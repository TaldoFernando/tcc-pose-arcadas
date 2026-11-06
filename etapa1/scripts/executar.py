"""Executa Etapa 1 somente nas cópias locais; resultados reproduzíveis."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MPLCONFIGDIR']='/private/tmp/goslon-etapa1-mpl'
from pathlib import Path
import sys,csv,json,hashlib,shutil,collections,itertools,time
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pose_normalize import read_triangles,sample_surface,center_pca,normalize_points,geodesic_deg,cloud,SIGNS,o3d
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'etapa1'; SEED=20261029

def csv_save(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def json_save(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))

def preview(tri,identifier,label):
    # Rasterização Matplotlib offline; simplificação quadric somente na prévia.
    fig=plt.figure(figsize=(12,4))
    mesh=o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(tri.reshape(-1,3)),o3d.utility.Vector3iVector(np.arange(tri.size//3).reshape(-1,3)))
    mesh.remove_duplicated_vertices()
    if len(tri)>18000: mesh=mesh.simplify_quadric_decimation(18000)
    faces=np.asarray(mesh.vertices)[np.asarray(mesh.triangles)]
    low=tri.reshape(-1,3).min(0); high=tri.reshape(-1,3).max(0);span=high-low; mid=(low+high)/2
    normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-20)
    light=np.array([.3,-.4,1.]);light/=np.linalg.norm(light);shade=.28+.65*np.abs(normals@light)
    colors=shade[:,None]*np.array([.65,.82,.95])[None,:]
    for i,(elev,azim) in enumerate([(25,40),(90,-90),(0,-90)]):
        ax=fig.add_subplot(1,3,i+1,projection='3d');ax.add_collection3d(Poly3DCollection(faces,facecolor=colors,edgecolor='none',linewidth=0,alpha=1))
        for j,fn in enumerate([ax.set_xlim,ax.set_ylim,ax.set_zlim]): fn(mid[j]-max(span)/2,mid[j]+max(span)/2)
        ax.set_box_aspect((1,1,1));ax.view_init(elev,azim);ax.set_xlabel('X');ax.set_ylabel('Y');ax.set_zlabel('Z')
        if i==1: ax.set_zticks([]);ax.set_zlabel('')
        if i==2: ax.set_yticks([]);ax.set_ylabel('')
    fig.suptitle(f'{identifier} — {label}',fontsize=11);fig.tight_layout();fig.savefig(OUT/'previews'/f'{identifier}.png',dpi=130);plt.close(fig)

def planes_ransac(tri):
    """Planos candidatos; não afirma que uma região plana é gesso."""
    points=sample_surface(tri,12000,SEED);remaining=points.copy();results=[]
    cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); areas=np.linalg.norm(cross,axis=1)/2
    normals=cross/np.maximum(2*areas[:,None],1e-20)
    for k in range(4):
        if len(remaining)<200: break
        o3d.utility.random.seed(SEED+k)
        model,indices=cloud(remaining).segment_plane(distance_threshold=.20,ransac_n=3,num_iterations=700,probability=.999)
        model=np.array(model);model/=np.linalg.norm(model[:3]); n=model[:3]
        distances=np.abs(tri@n+model[3]); angular=np.abs(normals@n)>=np.cos(np.radians(12))
        mask=(distances.max(axis=1)<=.25)&angular&(areas>0)
        frac=float(mask.mean());area_frac=float(areas[mask].sum()/areas.sum())
        results.append({'plano':model.tolist(),'triangulos':int(mask.sum()),'fracao_triangulos':frac,'fracao_area':area_frac,'inliers_amostra':len(indices)/12000})
        keep=np.ones(len(remaining),bool);keep[indices]=False;remaining=remaining[keep]
    best=max(results,key=lambda r:r['fracao_area'])
    # Critério operacional amplo; sujeito a falso positivo/negativo anatômico.
    probable=best['fracao_area']>=.04 and best['triangulos']>=100
    return {'base_detectada_operacional':probable,'status_base':'BASE_PROVAVEL_REVISAR' if probable else 'SEM_PLANO_GRANDE_DETECTADO_NAO_EXCLUI_BASE',
        'fracao_triangulos_base_candidata':best['fracao_triangulos'] if probable else 0.,
        'fracao_area_base_candidata':best['fracao_area'] if probable else 0.,'melhor_plano':best,'planos':results}

def main():
    rows=list(csv.DictReader((ROOT/'inventario.csv').open())); ids={r['arquivo']:f'STL{i+1:03d}' for i,r in enumerate(rows)}
    samples={};axes={}; copied=[]; groups=collections.defaultdict(list);hash_groups=collections.defaultdict(list)
    for r in rows:
        rel=r['arquivo'];src=ROOT/'dados'/rel;dst=OUT/'copias'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists(): shutil.copy2(src,dst)
        h=hashlib.sha256(dst.read_bytes()).hexdigest();assert h==r['sha256'],rel
        r['id']=ids[rel];r['copia']=str(dst.relative_to(OUT));groups[(r['grupo'],r['pasta_paciente'])].append(r);hash_groups[h].append(r)
        pts=sample_surface(read_triangles(dst));samples[r['id']]=pts;axes[r['id']]=center_pca(pts)[1]
        copied.append({'id':r['id'],'original':str(src),'copia':r['copia'],'sha256_antes':h})
    json_save('manifesto_copias.json',copied)
    pair=[]
    for (group,patient),rs in sorted(groups.items()):
        arch={a:[r for r in rs if r['arcada']==a] for a in ['superior','inferior']}
        # Preserva alternativas físicas, mas informa quantos conteúdos distintos há.
        notes=[]
        for a,items in arch.items():
            unique=len({r['sha256'] for r in items})
            if unique==0:notes.append(f'{a} ausente ou não identificada')
            if unique>1:notes.append(f'{a}: {unique} conteúdos diferentes, revisar sessão/pareamento')
            if len(items)>unique:notes.append(f'{a}: cópias idênticas presentes')
        others=[r['id'] for r in rs if r['arcada'] not in arch]
        if others:notes.append('revisão manual: '+', '.join(others))
        notes.append('agrupamento por pasta; identidade e oclusão não confirmadas')
        pair.append({'paciente':group+'/'+patient,'superior':json.dumps([r['copia'] for r in arch['superior']],ensure_ascii=False),'inferior':json.dumps([r['copia'] for r in arch['inferior']],ensure_ascii=False),'observacoes':'; '.join(notes)})
    csv_save('pareamento.csv',pair)
    templates={};selection=[]
    for category in ['superior','inferior','indeterminada','registro_mordida']:
        seen=set();members=[]
        for r in rows:
            if r['arcada']==category and r['sha256'] not in seen: members.append(r);seen.add(r['sha256'])
        A=[np.array(json.loads(r['pca_eixos_colunas'])) for r in members];D=np.zeros((len(A),len(A)))
        for i,j in itertools.combinations(range(len(A)),2):
            D[i,j]=D[j,i]=min(geodesic_deg(A[i].T@A[j]@s) for s in SIGNS)
        # Medoide angular: representante observado que minimiza soma de distâncias.
        idx=int(np.argmin(D.sum(axis=1)));chosen=members[idx];templates[category]=chosen
        shutil.copy2(OUT/chosen['copia'],OUT/'templates'/f'{category}.stl')
        selection.append({'categoria':category,'id':chosen['id'],'arquivo':chosen['copia'],'sha256':chosen['sha256'],'distancia_media_medoid_graus':float(D[idx].mean()),'metodo':'medoide angular PCA exata de superfície, 4 sinais, SHA256 únicos'})
    json_save('templates/selecao.json',selection)
    manual=[];units=[];bases=[];originals=[];trials=[];perfile=[];plane_cache={}
    rng=np.random.default_rng(SEED)
    for i,r in enumerate(rows):
        started=time.time();identifier=r['id'];tri=read_triangles(OUT/r['copia']);pts=samples[identifier];category=r['arcada'];template=samples[templates[category]['id']]
        # Bbox XYZ nativa e bbox PCA (largura/profundidade apenas aproximações geométricas).
        dims=np.ptp(tri.reshape(-1,3),axis=0);center,A,_=center_pca(pts);pdims=np.ptp((tri.reshape(-1,3)-center)@A,axis=0)
        incompatible=bool(max(pdims)>150 or pdims[0]<15 or pdims[1]<10)
        units.append({'id':identifier,'arquivo':r['copia'],'arcada':category,'largura_X_nativa_mm_assumido':dims[0],'profundidade_Y_nativa_mm_assumido':dims[1],'altura_Z_nativa_mm_assumido':dims[2],'largura_PCA1_mm_assumido':pdims[0],'profundidade_PCA2_mm_assumido':pdims[1],'espessura_PCA3_mm_assumido':pdims[2],'incompativel_mm_heuristica':incompatible,'observacoes':'limites geométricos de triagem, não validação anatômica; STL sem unidade'})
        if category in ['indeterminada','registro_mordida']:
            preview(tri,identifier,category)
            matches=sorted(set(x['arcada'] for x in hash_groups[r['sha256']] if x['arcada'] in ['superior','inferior']))
            manual.append({'id':identifier,'paciente':r['pasta_paciente'],'categoria':category,'arquivo':r['copia'],'preview':f'previews/{identifier}.png','coincidencia_sha256_com_arcada_nomeada':','.join(matches),'decisao_manual':''})
        h=r['sha256']
        if h not in plane_cache:plane_cache[h]=planes_ransac(tri)
        base=plane_cache[h].copy()
        if category=='registro_mordida' and base['base_detectada_operacional']:
            base['status_base']='PLANO_GRANDE_EM_REGISTRO_MORDIDA_NAO_CONFIRMA_BASE'
        bases.append({'id':identifier,'arquivo':r['copia'],'arcada':category,**{k:base[k] for k in ['base_detectada_operacional','status_base','fracao_triangulos_base_candidata','fracao_area_base_candidata']},'melhor_plano_fracao_triangulos':base['melhor_plano']['fracao_triangulos'],'melhor_plano_fracao_area':base['melhor_plano']['fracao_area'],'planos_json':json.dumps(base['planos'])})
        base_result=normalize_points(pts,template);R0=np.array(base_result['R']);t0=np.array(base_result['t']);originals.append({'id':identifier,'arquivo':r['copia'],'categoria':category,'template':templates[category]['id'],**base_result})
        errors=[]
        for k in range(20):
            Q=Rotation.random(random_state=rng).as_matrix();u=rng.uniform(-100,100,3); moved=pts@Q.T+u
            result=normalize_points(moved,template);R1=np.array(result['R']);t1=np.array(result['t'])
            # Normalização perturbada composta com transformação aplicada deve igualar baseline.
            error=geodesic_deg((R1@Q)@R0.T);translation_error=float(np.linalg.norm(R1@u+t1-t0));errors.append(error)
            trials.append({'id':identifier,'categoria':category,'ensaio':k+1,'erro_angular_graus':error,'erro_translacao_mm_assumido':translation_error,'falha_maior_5_graus':error>5,'RMSE':result['RMSE'],'fitness':result['fitness'],'Q':json.dumps(Q.tolist()),'u':json.dumps(u.tolist()),'R':json.dumps(result['R']),'t':json.dumps(result['t'])})
        perfile.append({'id':identifier,'arquivo':r['copia'],'categoria':category,'ensaios':20,'media_graus':float(np.mean(errors)),'desvio_populacional_graus':float(np.std(errors)),'max_graus':max(errors),'taxa_falha':float(np.mean(np.array(errors)>5)),'RMSE_original':base_result['RMSE']})
        # Checkpoints: uma interrupção não perde os ensaios já concluídos.
        csv_save('resultados/robustez_ensaios.csv',trials);csv_save('resultados/robustez_por_stl.csv',perfile);csv_save('bases.csv',bases);csv_save('unidades.csv',units)
        if manual:csv_save('revisao_manual.csv',manual)
        json_save('resultados/normalizacoes_originais.json',originals)
        print(f'{i+1}/{len(rows)} {identifier} {category} max={max(errors):.6f}° tempo={time.time()-started:.1f}s',flush=True)
    summary={}
    for category in ['superior','inferior','indeterminada','registro_mordida']:
        values=np.array([t['erro_angular_graus'] for t in trials if t['categoria']==category]);subset=[r for r in rows if r['arcada']==category]
        unique_ids={};
        for r in subset:unique_ids.setdefault(r['sha256'],r['id'])
        unique_values=np.array([t['erro_angular_graus'] for t in trials if t['id'] in unique_ids.values()])
        summary[category]={'stl':len(subset),'ensaios':len(values),'media_graus':float(values.mean()),'desvio_populacional_graus':float(values.std()),'max_graus':float(values.max()),'falhas':int((values>5).sum()),'taxa_falha':float((values>5).mean()),'sem_duplicatas':{'stl':len(unique_ids),'media_graus':float(unique_values.mean()),'desvio_graus':float(unique_values.std()),'max_graus':float(unique_values.max()),'taxa_falha':float((unique_values>5).mean())}}
        fig,ax=plt.subplots(figsize=(7,4));ax.hist(values,bins=np.linspace(0,180,37),color='#377f9e');ax.axvline(5,color='red',linestyle='--',label='Falha >5°');ax.set(xlabel='Erro angular geodésico (graus)',ylabel='Ensaios',title=f'Robustez — {category} (n={len(values)})');ax.legend();fig.tight_layout();fig.savefig(OUT/'resultados'/f'histograma_{category}.png',dpi=150);plt.close(fig)
    json_save('resultados/robustez_resumo.json',summary)
    # Confere tanto as fontes quanto as cópias após toda a execução.
    validation=[]
    for entry in copied:
        before=entry['sha256_antes'];source_hash=hashlib.sha256(Path(entry['original']).read_bytes()).hexdigest();copy_hash=hashlib.sha256((OUT/entry['copia']).read_bytes()).hexdigest()
        assert before==source_hash==copy_hash
        validation.append({'id':entry['id'],'original_inalterado':True,'copia_identica':True,'sha256':source_hash})
    json_save('validacao_integridade.json',validation)
    json_save('parametros.json',{'seed':SEED,'samples_icp':2048,'icp_max_iterations':60,'icp_correspondence_distance_mm_assumido':8,'ransac_samples':12000,'ransac_distance_mm_assumido':.20,'ransac_iterations_por_plano':700,'max_planos':4,'triangulos_plano_distancia_max_mm_assumido':.25,'normal_angulo_max_graus':12,'base_fracao_area_min':.04,'base_min_triangulos':100,'robustez_por_stl':20,'translacoes_uniforme_mm_assumido':[-100,100],'rotacoes':'Haar uniforme SO(3), scipy Rotation.random','falha_graus':5,'unit_triage':{'maior_dim_max':150,'pca1_min':15,'pca2_min':10},'open3d':o3d.__version__})
    print('CONCLUIDO',flush=True)
if __name__=='__main__': main()
