"""Renderização e features locais do MODELO SUBSTITUTO; nenhum rótulo no registro."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json,time,hashlib,argparse,concurrent.futures
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa7b';SEED=20261106
sys.path[:0]=[str(ROOT/'etapa6'),str(ROOT/'etapa5')]
from render_views import read_stl,prepare_mesh,render_views,VIEWS
from anatomical_pair import normalize_anatomical
from pca_pair import normalize_pair_points
from rigid_icp import sample_surface
AXES={'vertical':2,'anteroposterior':1,'lateral':0}
def load(p):return json.loads(Path(p).read_text())
def moved(mesh,R,t):
 return {'_prepared':True,'arches':{a:{'triangles':np.ascontiguousarray(v['triangles']@R.T+t),'normals':np.ascontiguousarray(v['normals']@R.T)} for a,v in mesh['arches'].items()}}
def angle(R):return float(np.linalg.norm(Rotation.from_matrix(R).as_rotvec())*180/np.pi)
def rotation(axis,degrees):
 v=np.zeros(3);v[AXES[axis]]=np.deg2rad(degrees);return Rotation.from_rotvec(v).as_matrix()
def descriptors(images):
 values=[]
 for im in images:
  gray=im.mean(2);mask=np.max(abs(im.astype(float)-32),2)>5;y,x=np.where(mask);h,w=mask.shape
  if len(x):values.extend([mask.mean(),x.mean()/w,y.mean()/h,(x.max()-x.min()+1)/w,(y.max()-y.min()+1)/h,gray[mask].mean()/255,gray[mask].std()/255,(np.abs(np.diff(mask.astype(float),axis=0)).sum()+np.abs(np.diff(mask.astype(float),axis=1)).sum())/(w+h)])
  else:values.extend([0.]*8)
 return np.array(values,np.float32)
def worker(identifier):
 start=time.monotonic();target=OUT/'features'/f'{identifier}.npz';target.parent.mkdir(exist_ok=True)
 if target.exists():return identifier,'cached',round(time.monotonic()-start,2)
 import torch
 from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(SEED)
 net=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1).features.eval();net.requires_grad_(False)
 mean=torch.tensor([.485,.456,.406])[None,:,None,None];std=torch.tensor([.229,.224,.225])[None,:,None,None]
 cfg=load(OUT/'camera_config_proprio.json');pairs={p['id']:p for p in load(ROOT/'etapa5/pares_ids.json')};p=pairs[identifier]
 orig=prepare_mesh({a:read_stl(ROOT/'etapa5'/p[a]['arquivo']) for a in ['superior','inferior']})
 canonical={r['ID']:r for r in load(ROOT/'etapa6/stl/transformacoes.json')}[identifier];R0=np.array(canonical['R']);t0=np.array(canonical['t']);base=moved(orig,R0,t0)
 clouds=np.load(ROOT/'etapa5/clouds'/f'{identifier}.npz');u=clouds['superior_base'];l=clouds['inferior_base'];center=((u@R0.T+t0).mean(0)+(l@R0.T+t0).mean(0))/2
 model=np.load(ROOT/'etapa6/stl/modelo_normalizacao.npz');F=model['canonical_F'];ids=model['IDs'].tolist();templates=[(model[f'upper_{k}'],model[f'lower_{k}']) for k in range(5)]
 def composed(fit,k):
  r=F.T@model[f'C_R_{k}']@np.array(fit['R']);t=F.T@(model[f'C_R_{k}']@np.array(fit['t'])+model[f'C_t_{k}'])
  return {'R':r,'t':t,'RMSE':fit['RMSE'],'template':ids[k]}
 def fits(uu,ll):
  candidates=[normalize_anatomical(uu,ll,*template,1.,'pca_sign') for template in templates]
  k=min(range(5),key=lambda i:(candidates[i]['RMSE'],i))
  return {'controle':composed(normalize_pair_points(uu,ll,*templates[0],'combinada'),0),'anatomica':composed(candidates[0],0),'multi5_rmse':composed(candidates[k],k)}
 baseline=fits(u,l)
 # Estes ajustes não usam rótulos nem a transformação conhecida da avaliação.
 records=[];features=[];desc=[];pending=[];pendingmeta=[];hashes=[];pixelcache={};render_seconds=0.;fit_seconds=0.
 def flush():
  if not pending:return
  images=np.stack(pending).reshape(-1,224,224,3)
  tensor=torch.from_numpy(images.copy()).permute(0,3,1,2).float()/255
  with torch.inference_mode():emb=net((tensor-mean)/std).mean((2,3)).reshape(len(pending),6,576).numpy()
  for j,(meta,im,hh) in enumerate(pendingmeta):
   records.append(meta);features.append(emb[j]);desc.append(descriptors(im));hashes.append(hh)
  pending.clear();pendingmeta.clear()
 def emit(mesh,kind,method='nenhuma',axis='nenhum',deg=0.,sign=0,trial=-1,pose_error=0.,rmse=0.,template='',augmentation=0):
  nonlocal render_seconds
  s=time.monotonic();views=render_views(mesh,cfg);im=np.stack([views[v] for v in VIEWS]);render_seconds+=time.monotonic()-s
  hh=hashlib.sha256(im.tobytes()).hexdigest();meta={'ID':identifier,'condition':kind,'method':method,'axis':axis,'angle':deg,'sign':sign,'trial':trial,'pose_error_deg':pose_error,'rmse':rmse,'template_ID':template,'augmentation':augmentation,'empty_views':int(sum(np.max(abs(x.astype(float)-32))<=5 for x in im))}
  if kind=='canonical':
   d=OUT/'previews'/identifier;d.mkdir(parents=True,exist_ok=True)
   from PIL import Image
   for v,x in views.items():Image.fromarray(x).save(d/f'{v}.png')
  pending.append(im);pendingmeta.append((meta,im,hh))
  if len(pending)>=8:flush()
 emit(base,'canonical')
 for limit in [10,20]:
  rng=np.random.default_rng(SEED+5000+100*int(identifier[1:])+limit)
  for j in range(6):
   ax=str(rng.choice(list(AXES)));deg=float(rng.uniform(-limit,limit));q=rotation(ax,deg)
   emit(moved(base,q,center-q@center),'augmentation',axis=ax,deg=abs(deg),sign=int(np.sign(deg)),trial=j,augmentation=limit)
 for ax in AXES:
  for deg in [2,3,5,10,20]:
   for sign in [-1,1]:
    q=rotation(ax,sign*deg);shift=center-q@center
    emit(moved(base,q,shift),'rotation',axis=ax,deg=deg,sign=sign,pose_error=deg)
    # Conjuga a perturbação canônica ao STL nativo; os registradores não recebem q.
    Q=R0.T@q@R0;tr=R0.T@(q@t0+shift-t0)
    s=time.monotonic();ff=fits(u@Q.T+tr,l@Q.T+tr);fit_seconds+=time.monotonic()-s
    for name,f in ff.items():
     R=f['R']@Q;t=f['R']@tr+f['t'];err=angle(R@baseline[name]['R'].T)
     emit(moved(orig,R,t),'rotation',name,ax,deg,sign,pose_error=err,rmse=f['RMSE'],template=f['template'])
 for trial in range(20):
  key=f'{trial:02d}';Q=clouds[f'Q{key}'];tr=clouds[f't{key}'];uu=clouds[f'superior{key}'];ll=clouds[f'inferior{key}']
  # Reproduz exatamente a escolha das malhas decimadas do gerador de nuvens.
  rng=np.random.default_rng(20261105+1000*int(identifier[1:])+trial);Rotation.random(random_state=rng);rng.uniform(-100,100,3);tri={}
  for a in ['superior','inferior']:
   level=str(rng.choice(['leve','forte']));tri[a]=np.load(ROOT/'etapa5/cache'/identifier/f'{a}_{level}.npz')['tri'];ps=int(rng.integers(1,2**31));points=sample_surface(tri[a],2048,ps);rng.normal(0,.15,points.shape);rng.uniform(.10,.30);rng.integers(len(points))
  dec=prepare_mesh(tri)
  emit(moved(dec,R0@Q,R0@tr+t0),'realistic',trial=trial,pose_error=angle(R0@Q@R0.T))
  s=time.monotonic();cached=[]
  for k,tid in enumerate(ids):
   path=ROOT/'etapa5/cache_pose'/identifier/f'{tid}.json'
   cached.append(load(path) if path.exists() else {})
  candidates=[c['anatomica'][trial+1] if len(c.get('anatomica',[]))==21 else normalize_anatomical(uu,ll,*templates[k],1.,'pca_sign') for k,c in enumerate(cached)]
  k=min(range(5),key=lambda i:(candidates[i]['RMSE'],i));c=cached[0]
  control=c['controle'][trial+1] if len(c.get('controle',[]))==21 else normalize_pair_points(uu,ll,*templates[0],'combinada')
  ff={'controle':composed(control,0),'anatomica':composed(candidates[0],0),'multi5_rmse':composed(candidates[k],k)};fit_seconds+=time.monotonic()-s
  for name,f in ff.items():
   R=f['R']@Q;t=f['R']@tr+f['t'];err=angle(R@baseline[name]['R'].T)
   emit(moved(dec,R,t),'realistic',name,trial=trial,pose_error=err,rmse=f['RMSE'],template=f['template'])
 flush();np.savez_compressed(target,features=np.array(features,np.float32),descriptors=np.array(desc,np.float32),records=np.array(json.dumps(records)),pixel_hashes=np.array(hashes),baseline_pose=np.array(json.dumps({n:{'R':f['R'].tolist(),'t':f['t'].tolist(),'RMSE':f['RMSE'],'template':f['template']} for n,f in baseline.items()})))
 timing={'ID':identifier,'cases':len(records),'render_seconds':render_seconds,'fit_seconds':fit_seconds,'total_seconds':time.monotonic()-start};(target.with_suffix('.json')).write_text(json.dumps(timing,indent=2));return timing
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--ids',nargs='*');a=p.parse_args()
 if not (OUT/'congelamento.json').exists():raise SystemExit('Congele o protocolo antes.')
 selected=a.ids or [u['ID'] for u in load(OUT/'unidades.json')]
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
  futures={pool.submit(worker,i):i for i in selected}
  for f in concurrent.futures.as_completed(futures):print('FEATURES',f.result(),flush=True)
