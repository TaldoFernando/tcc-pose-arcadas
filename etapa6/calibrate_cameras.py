"""Calibração supervisionada por imagens locais pareadas; nunca executa ao importar.

Não há dados pareados de treino confirmados nesta entrega. Fornecer manifest
com IDs, hashes de conteúdo, arquivos locais e comprovação de origem.
"""
from pathlib import Path
import copy,csv,hashlib,json,re,time
import numpy as np
from PIL import Image
from scipy.optimize import differential_evolution,minimize
from scipy.spatial.transform import Rotation
from render_views import VIEWS,prepare_mesh,read_stl,render_one,camera_basis
from metrics import estimate_background,compare_images,foreground,objective


def make_camera(parameters,base,projection,radius):
    rx,ry,rz,dx,dy,extent=parameters[:6];rotation=Rotation.from_rotvec(np.deg2rad([rx,ry,rz])).as_matrix();pos,basis=camera_basis(base);B=rotation@basis
    # Translation along optical axis and orthographic distance are not identifiable.
    target=np.asarray(base['target'],float)+radius*(dx*B[:,0]+dy*B[:,1]);distance=radius*4
    camera=copy.deepcopy(base);camera.update(projection=projection,position=(target-B[:,2]*distance).tolist(),target=target.tolist(),up=B[:,1].tolist())
    if projection=='orthographic':camera['ortho_height']=radius*np.exp(extent)
    else:
        distance=radius*np.exp(parameters[6]);camera['position']=(target-B[:,2]*distance).tolist();camera['fov_y_deg']=float(np.rad2deg(2*np.arctan(radius*np.exp(extent)/(2*distance))));camera.pop('ortho_height',None)
    return camera


def _native_pair(mesh,camera,appearance,reference,mask):
    image,render_mask=render_one(mesh,camera,appearance);return image,reference,render_mask,mask

def optimize_view(records,view,base,appearance,seed=20261106,budget=25):
    # Image dimensions and RGB background are observed in calibration only.
    references=[np.asarray(Image.open(r['images'][view]).convert('RGB')) for r in records];sizes={tuple(im.shape[:2][::-1]) for im in references}
    if len(sizes)!=1:raise ValueError('Resoluções de calibração variáveis; estratificar a origem antes de ajustar câmeras')
    base=copy.deepcopy(base);base['resolution']=list(next(iter(sizes)));base['background']=np.median([estimate_background(im) for im in references],axis=0).round().astype(int).tolist();masks=[foreground(im) for im in references]
    meshes=[r['_mesh'] for r in records];points=np.concatenate([a['triangles'].reshape(-1,3) for mesh in meshes for a in mesh['arches'].values()]);radius=float(np.linalg.norm(np.ptp(points,axis=0))/2)
    if radius<=0:raise ValueError('Malha degenerada')
    # Coarse comparisons share an explicitly resized calibration grid; final metrics use native pixels.
    coarse=[];W,H=base['resolution'];factor=min(1,192/max(W,H));cw,ch=max(8,round(W*factor)),max(8,round(H*factor));base_coarse=copy.deepcopy(base);base_coarse['resolution']=[cw,ch]
    for image in references:coarse.append(np.asarray(Image.fromarray(image).resize((cw,ch),Image.Resampling.LANCZOS)))
    coarse_masks=[foreground(im) for im in coarse];candidates=[]
    for projection in ['orthographic','perspective']:
        bounds=[(-180,180),(-180,180),(-180,180),(-.6,.6),(-.6,.6),(.1,1.5)]+([(np.log(2),np.log(10))] if projection=='perspective' else [])
        def loss(p):
            camera=make_camera(p,base_coarse,projection,radius);scores=[]
            for mesh,reference,mask in zip(meshes,coarse,coarse_masks):
                render,rm=render_one(mesh,camera,appearance);scores.append(objective(compare_images(render,reference,rm,mask),reference.shape))
            return float(np.mean(scores))
        solution=differential_evolution(loss,bounds,seed=seed,maxiter=budget,popsize=6,polish=False,updating='immediate',workers=1,tol=1e-5);local=minimize(loss,solution.x,method='Powell',bounds=bounds,options={'maxiter':40,'xtol':.01,'ftol':1e-5})
        p=local.x if local.fun<solution.fun else solution.x;score=min(local.fun,solution.fun);camera=make_camera(p,base,projection,radius)
        candidates.append({'camera':camera,'calibration_loss':float(score),'projection':projection,'parameters':p.tolist(),'orthographic_distance_status':'FIXED_GAUGE_NOT_IDENTIFIABLE' if projection=='orthographic' else 'ESTIMATED_CONDITIONALLY','radius':radius})
    best=min(candidates,key=lambda c:c['calibration_loss']);projection=best['projection'];bounds=[(-180,180)]*3+[(-.6,.6),(-.6,.6),(.1,1.5)]+([(np.log(2),np.log(10))] if projection=='perspective' else [])
    def native_loss(p):
        camera=make_camera(p,base,projection,radius)
        return float(np.mean([objective(compare_images(*_native_pair(mesh,camera,appearance,reference,mask)),reference.shape) for mesh,reference,mask in zip(meshes,references,masks)]))
    # Native resolution refinement, still calibration only; finite declared budget.
    result=minimize(native_loss,best['parameters'],method='Powell',bounds=bounds,options={'maxfev':80,'xtol':1e-4,'ftol':1e-5});p=result.x if result.fun<native_loss(best['parameters']) else np.array(best['parameters']);best['coarse_calibration_loss']=best['calibration_loss'];best['native_calibration_loss']=native_loss(p);best['camera']=make_camera(p,base,projection,radius);best['parameters']=p.tolist()
    return best,candidates


def load_records(path):
    manifest=json.loads(Path(path).read_text());records=manifest['records'];by_content={}
    for r in records:
        if not re.fullmatch(r'P\d{3}',r['ID']):raise ValueError('Somente IDs P001...')
        if r.get('confirmed_pair') is not True or r.get('confirmed_training_source') is not True:raise ValueError('Pareamento e origem de treino precisam ser comprovados, não inferidos apenas por aparência')
        if set(r['images'])!=set(VIEWS):raise ValueError('Faltam vistas em um ID')
        if set(r['meshes'])!={'superior','inferior'}:raise ValueError('Calibração requer par superior/inferior')
        try:raw={a:read_stl(p) for a,p in r['meshes'].items()}
        except Exception:raise ValueError('ID '+r['ID']+': STL local ausente ou inválido') from None
        actual=hashlib.sha256('|'.join(hashlib.sha256(Path(r['meshes'][a]).read_bytes()).hexdigest() for a in ['superior','inferior']).encode()).hexdigest();r['content_sha256']=actual
        transform=r.get('fixed_input_transform',{'R':np.eye(3).tolist(),'t':[0,0,0]});R=np.asarray(transform['R'],float);t=np.asarray(transform['t'],float)
        if not np.allclose(R.T@R,np.eye(3),atol=1e-6) or abs(np.linalg.det(R)-1)>1e-6:raise ValueError('Transformação de entrada precisa ser rígida própria')
        r['_mesh']=prepare_mesh({a:tri@R.T+t for a,tri in raw.items()});role=r['split']
        if role not in ['calibration','validation']:raise ValueError('split inválido')
        key=r['content_sha256'];previous=by_content.setdefault(key,role)
        if previous!=role:raise ValueError('Conteúdo idêntico atravessa calibração/validação')
    return manifest


def run(manifest_path,initial_config_path,output_dir):
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True);manifest=load_records(manifest_path);records=manifest['records'];dev=[r for r in records if r['split']=='calibration'];test=[r for r in records if r['split']=='validation']
    if not dev or not test:raise ValueError('Calibração e validação independentes obrigatórias')
    cfg=json.loads(Path(initial_config_path).read_text());history={}
    # All camera/model choices use calibration only. No fitted per-patient image transform.
    for i,view in enumerate(VIEWS):
        best,alternatives=optimize_view(dev,view,cfg['views'][view],cfg['appearance'],manifest.get('seed',20261106)+i);cfg['views'][view]=best['camera'];cfg['views'][view]['parameter_status']={'pose':'FITTED_WITH_GAUGE','resolution':'OBSERVED_IN_CALIBRATION','background':'ESTIMATED_FROM_CALIBRATION_CORNERS','distance':'PLACEHOLDER_UNIDENTIFIABLE_GAUGE' if best['projection']=='orthographic' else 'FITTED_CONDITIONALLY','near_far':'PLACEHOLDER_FIXED_CLIPPING_RANGE','light_material':'PLACEHOLDER_FIXED_CONTROLLED','input_pose':'FIXED_PRECOMPUTED_RIGID_TRANSFORM_NOT_FITTED_TO_IMAGES'};history[view]=alternatives
    cfg['status']='CALIBRATED';cfg.pop('allow_uncalibrated',None);cfg['calibration_IDs']=[r['ID'] for r in dev];cfg['validation_IDs']=[r['ID'] for r in test];cfg['source']='local confirmed paired images; source mapping stays private';cfg['appearance_training_status']='PLACEHOLDER: fixed controlled material/light; not inferred from STL texture';frozen=json.dumps(cfg,ensure_ascii=False,indent=2);(output/'camera_config.json').write_text(frozen);(output/'congelamento_cameras.json').write_text(json.dumps({'config_sha256':hashlib.sha256(frozen.encode()).hexdigest(),'utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'model_choices':'calibration only'},indent=2))
    rows=[]
    for r in test:
        for view in VIEWS:
            camera=cfg['views'][view];reference=np.asarray(Image.open(r['images'][view]).convert('RGB'));start=time.perf_counter();image,mask=render_one(r['_mesh'],camera,cfg['appearance']);elapsed=time.perf_counter()-start
            if image.shape!=reference.shape:raise ValueError('Validação tem resolução diferente: reportar incompatibilidade, sem adaptar configuração ao teste')
            rows.append({'ID':r['ID'],'view':view,**compare_images(image,reference,mask),'seconds':elapsed})
    with (output/'validacao_por_ID.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={}
    for view in VIEWS:
        rs=[r for r in rows if r['view']==view];summary[view]={k:{'median':float(np.median([r[k] for r in rs])),'max':float(np.max([r[k] for r in rs])),'min':float(np.min([r[k] for r in rs]))} for k in ['IoU','SSIM','centroid_px','scale_percent','bbox_error_px']}
    (output/'validacao_resumo.json').write_text(json.dumps(summary,indent=2));(output/'calibracao_historico.json').write_text(json.dumps(history,indent=2))
    if len(test)>=10:
        from contact_sheet import make_contact_sheet
        selected=make_contact_sheet(test,cfg,output/'folha_10_validacao.png',manifest.get('seed',20261106));(output/'folha_IDs.json').write_text(json.dumps(selected))
    else:(output/'folha_status.json').write_text(json.dumps({'status':'LESS_THAN_10_VALIDATION_IDS','available':len(test),'requested':10}))
    return cfg,rows

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('initial_config');parser.add_argument('output_dir');args=parser.parse_args();run(args.manifest,args.initial_config,args.output_dir)
