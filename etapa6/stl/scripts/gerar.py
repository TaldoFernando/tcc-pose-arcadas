from pathlib import Path
import os,sys,json,csv,time,hashlib,copy,multiprocessing
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'etapa6';OUT=BASE/'stl';sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT/'etapa5'))
from stl_views import normalize_pair
from render_views import read_stl,prepare_mesh,render_views,camera_basis,VIEWS,render_one
from anatomical_pair import anatomical_frame
from PIL import Image,ImageDraw

def load(path):return json.loads(Path(path).read_text())
def save(path,data):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2))
def csvsave(path,rows):
 with Path(path).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def normalize_job(record):
 start=time.perf_counter();mesh={a:ROOT/'etapa5'/record[a]['arquivo'] for a in ['superior','inferior']};cfg={'normalization_model':'stl/modelo_normalizacao.npz'};_,result=normalize_pair(mesh,cfg);return {'ID':record['id'],**result,'seconds':time.perf_counter()-start}

def transformed(record,fit):
 R=np.asarray(fit['R']);t=np.asarray(fit['t']);return {a:read_stl(ROOT/'etapa5'/record[a]['arquivo'])@R.T+t for a in ['superior','inferior']}

def render_job(job):
 record,fit,group,split=job;cfg=load(BASE/'camera_config.json');start=time.perf_counter();mesh=transformed(record,fit);prepared=prepare_mesh(mesh);prep=time.perf_counter()-start;start=time.perf_counter();images=render_views(prepared,cfg);render_time=time.perf_counter()-start;directory=OUT/'imagens'/f'grupo_{group}'/record['id'];directory.mkdir(parents=True,exist_ok=True);rows=[];coverage=[]
 for name,image in images.items():
  path=directory/f'{name}.png';Image.fromarray(image).save(path);camera=cfg['views'][name];pos,B=camera_basis(camera);points=np.concatenate([mesh[a].reshape(-1,3) for a in mesh if camera['mesh']=='ambas' or a==camera['mesh']]);q=(points-pos)@B;half=camera['ortho_height']/2;outside=(abs(q[:,0])>half)|(abs(q[:,1])>half);coverage.append({'ID':record['id'],'view':name,'fraction_vertices_outside_frame':float(outside.mean()),'clipping_detected':bool(outside.any())})
  rows.append({'ID':record['id'],'grupo':group,'split':split,'view':name,'arquivo':str(path.relative_to(BASE)),'sha256_png':sha(path),'sha256_pixels':hashlib.sha256(image.tobytes()).hexdigest()})
 return rows,coverage,{'ID':record['id'],'grupo':group,'normalization_seconds':fit['seconds'],'prepare_seconds':prep,'six_views_seconds':render_time,'total_compute_seconds':fit['seconds']+prep+render_time,'RMSE':fit['RMSE'],'template_ID':fit['template_ID']}

def contact(IDs,groups,path,cell=160):
 sheet=Image.new('RGB',(90+6*cell,42+len(IDs)*(cell+16)),(245,245,245));d=ImageDraw.Draw(sheet)
 for j,v in enumerate(VIEWS):d.text((90+j*cell+5,15),v,fill='black')
 for n,i in enumerate(IDs):
  y=42+n*(cell+16);d.text((4,y+12),i,fill='black');d.text((4,y+30),'Grupo '+str(groups[i]),fill='black')
  for j,v in enumerate(VIEWS):
   im=Image.open(OUT/'imagens'/f'grupo_{groups[i]}'/i/f'{v}.png');im.thumbnail((cell-4,cell-4));sheet.paste(im,(90+j*cell,y))
 sheet.save(path)

def main():
 OUT.mkdir(exist_ok=True);pairs=load(ROOT/'etapa5/pares_ids.json');byid={p['id']:p for p in pairs};split=load(ROOT/'etapa5/divisao_original.json');bank=load(ROOT/'etapa5/referencias/banco_original.json');raw0=np.load(ROOT/'etapa5/templates_raw/P016.npz');F,_=anatomical_frame(raw0['upper'],raw0['lower'],1.,'pca_sign');model={'canonical_F':F,'IDs':np.array([r['id'] for r in bank])}
 for k,b in enumerate(bank):
  raw=np.load(ROOT/'etapa5/templates_raw'/f"{b['id']}.npz");C=np.array(b['alignment']['R']);t=np.array(b['alignment']['t']);model[f'upper_{k}']=raw['upper'];model[f'lower_{k}']=raw['lower'];model[f'C_R_{k}']=C;model[f'C_t_{k}']=C@raw['origin']+t
 np.savez_compressed(OUT/'modelo_normalizacao.npz',**model)
 with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
  fits=list(pool.map(normalize_job,pairs))
 fitby={r['ID']:r for r in fits};save(OUT/'transformacoes.json',fits);print('NORMALIZADOS',len(fits),flush=True)
 # Geometria de desenvolvimento, sem rótulos e sem imagens de referência.
 specs={'Angulada':([np.sin(np.deg2rad(35))*np.cos(np.deg2rad(20)),-np.cos(np.deg2rad(35))*np.cos(np.deg2rad(20)),np.sin(np.deg2rad(20))],[0,0,1],'ambas'),'Direita':([1,0,0],[0,0,1],'ambas'),'Esquerda':([-1,0,0],[0,0,1],'ambas'),'Up':([0,0,1],[0,-1,0],'superior'),'Frontal':([0,-1,0],[0,0,1],'ambas'),'Inferior':([0,0,-1],[0,1,0],'inferior')};bounds={};basis={}
 for name,(direction,up,arch) in specs.items():
  _,B=camera_basis({'position':(np.array(direction)*200).tolist(),'target':[0,0,0],'up':up});basis[name]=B;bounds[name]=[np.full(3,np.inf),np.full(3,-np.inf)]
 for i in split['desenvolvimento']:
  mesh=transformed(byid[i],fitby[i])
  for name,(_,_,arch) in specs.items():
   p=np.concatenate([v.reshape(-1,3) for a,v in mesh.items() if arch=='ambas' or a==arch])@basis[name];bounds[name][0]=np.minimum(bounds[name][0],p.min(0));bounds[name][1]=np.maximum(bounds[name][1],p.max(0))
 views={}
 for name,(direction,up,arch) in specs.items():
  lo,hi=bounds[name];target=basis[name]@((lo+hi)/2);views[name]={'projection':'orthographic','position':(target+np.array(direction)*200).tolist(),'target':target.tolist(),'up':up,'ortho_height':float(max((hi-lo)[:2])*1.20),'resolution':[512,512],'near':.1,'far':1000.,'background':[32,32,32],'mesh':arch,'parameter_status':'DEFINED_STL_PROTOCOL_NOT_FITTED_TO_LEGACY_TRAINING'}
 cfg={'schema_version':2,'status':'STANDARDIZED_STL','allow_uncalibrated':False,'purpose':'new deterministic six-view protocol using STL geometry only, authorized by user','normalization_model':'stl/modelo_normalizacao.npz','normalization':'original multi5_rmse bank from development, proper rigid transform shared by both arches, no scaling','groups_used_for_geometry':False,'calibration_source':'normalized STL bounds of original 20 development IDs only; 20% fixed margin','camera_fit_IDs':split['desenvolvimento'],'heldout_IDs':split['teste'],'previous_training_equivalence':'NOT_EVALUATED_OUTSIDE_CURRENT_SCOPE','legacy_training_parameters':'PLACEHOLDER_NOT_NEEDED_FOR_NEW_STL_PROTOCOL','views':views,'appearance':{'background':[32,32,32],'material_rgb':[220,220,220],'ambient':.35,'diffuse':.65,'light_direction_camera':[-.3,.5,-1.],'shading':'smooth','two_sided':True,'supersampling':2},'angle_definition':{'Angulada_azimuth_deg':35,'Angulada_elevation_deg':20,'Direita':'camera on canonical +X; clinical laterality not certified','Esquerda':'camera on canonical -X; clinical laterality not certified'},'scale_units':'native STL, provisionally interpreted as mm; no per-patient zoom','model_base_treatment':'preserve all original triangles; no trimming'}
 save(BASE/'camera_config.json',cfg);save(OUT/'congelamento.json',{'camera_sha256':sha(BASE/'camera_config.json'),'model_sha256':sha(OUT/'modelo_normalizacao.npz'),'code_sha256':{str(p.relative_to(BASE)):sha(p) for p in [BASE/'render_views.py',BASE/'stl_views.py',Path(__file__)]},'fit_uses_development_only':True,'utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()});print('CAMERAS CONGELADAS ANTES DA AVALIACAO DE ENQUADRAMENTO',flush=True)
 # Rótulos são lidos somente agora, para pastas e relatórios, após as câmeras.
 labels={r['ID']:int(r['grupo']) for r in csv.DictReader((ROOT/'etapa5/rotulos_local.csv').open())};jobs=[(p,fitby[p['id']],labels[p['id']],'desenvolvimento' if p['id'] in split['desenvolvimento'] else 'teste') for p in pairs]
 with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:results=list(pool.map(render_job,jobs))
 images=[r for a,_,_ in results for r in a];coverage=[r for _,b,_ in results for r in b];times=[r for _,_,r in results];csvsave(OUT/'manifesto_imagens.csv',images);csvsave(OUT/'enquadramento.csv',coverage);csvsave(OUT/'tempo_por_ID.csv',times);csvsave(OUT/'rotulos.csv',[{'ID':i,'grupo':labels[i],'fonte':'grupo informado pelo usuário; nome da pasta original'} for i in sorted(labels)])
 rng=np.random.default_rng(20261106);selected=[]
 for g,n in [(1,4),(2,3),(3,3)]:
  IDs=sorted(i for i in labels if labels[i]==g);selected+=sorted(rng.choice(IDs,n,replace=False).tolist());contact(IDs,labels,OUT/f'contato_grupo_{g}.png')
 contact(selected,labels,OUT/'folha_10_IDs.png');save(OUT/'selecao_visual.json',{'seed':20261106,'IDs':selected,'counts_per_group':{'1':4,'2':3,'3':3}})
 clusters={}
 for p in pairs:clusters.setdefault(p['superior']['sha256']+'|'+p['inferior']['sha256'],[]).append(p['id'])
 duplicates=[{'IDs':','.join(ids),'grupos':','.join(str(labels[i]) for i in ids),'grupos_divergentes':len({labels[i] for i in ids})>1} for ids in clusters.values() if len(ids)>1];csvsave(OUT/'duplicatas_conteudo.csv',duplicates)
 summary={'status':'STL_ONLY_STANDARDIZED_PROTOCOL','patient_IDs':len(pairs),'unique_pair_contents':len(clusters),'images':len(images),'groups':{str(g):{'n_IDs':sum(labels[i]==g for i in labels),'n_images':sum(r['grupo']==g for r in images),'median_render_seconds':float(np.median([r['six_views_seconds'] for r in times if r['grupo']==g]))} for g in [1,2,3]},'median_normalization_seconds':float(np.median([r['seconds'] for r in fits])),'median_six_views_seconds':float(np.median([r['six_views_seconds'] for r in times])),'IDs_with_any_frame_clipping':sorted({r['ID'] for r in coverage if r['clipping_detected']}),'legacy_images_used':False,'labels_used_in_normalization_or_camera_fit':False,'duplicate_content_group_conflicts':[r for r in duplicates if r['grupos_divergentes']]};save(OUT/'resumo.json',summary);print('CONCLUIDO',len(images),'imagens',flush=True)
if __name__=='__main__':main()
