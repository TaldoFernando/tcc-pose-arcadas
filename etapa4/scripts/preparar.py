from common import *
from replay import baseline_points
from anatomical_pair import normalize_anatomical,anatomical_frame
import shutil
manifest=[];pairs=load_json('pares.json');split=load_json('divisao.json')
for p in pairs:
 for a in ['superior','inferior']:
  source=ROOT/'etapa3'/p[a]['arquivo'];target=OUT/p[a]['arquivo'];target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():shutil.copy2(source,target)
  assert digest(target)==p[a]['sha256']
  manifest.append({'id':p['id'],'arcada':a,'copia':str(target.relative_to(OUT)),'fonte':str(source),'original':str(ROOT/'dados'/p[a]['fonte_inventario']),'sha256':p[a]['sha256']})
 for a in ['superior','inferior']:
  for level in ['leve','forte']:
   source=ROOT/'etapa3/cache'/p['id']/f'{a}_{level}.npz';target=OUT/'cache'/p['id']/source.name;target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists():shutil.copy2(source,target)
save_json('manifesto_copias.json',manifest)
# Escolha de 5 templates pareados, exclusivamente entre 17 conteúdos do desenvolvimento.
dev=[];seen=set();descriptors=[]
for p in pairs:
 if p['id'] not in split['desenvolvimento']:continue
 h=(p['superior']['sha256'],p['inferior']['sha256'])
 if h in seen:continue
 seen.add(h);dev.append(p);u,l=baseline_points(p);F,_=anatomical_frame(u,l,1.,'pca_sign')
 descriptors.append(np.concatenate([np.ptp((u-u.mean(0))@F,axis=0),np.ptp((l-l.mean(0))@F,axis=0)]))
X=np.array(descriptors);X=(X-X.mean(0))/np.maximum(X.std(0),1e-8)
selected=[next(i for i,p in enumerate(dev) if p['id']=='P016')]
while len(selected)<5:
 distances=np.min(np.linalg.norm(X[:,None,:]-X[selected][None,:,:],axis=2),axis=1);distances[selected]=-1;selected.append(int(np.argmax(distances)))
primary=dev[selected[0]];tu,tl=baseline_points(primary)
# Mesmas sementes do template Etapa 3 para preservar o sistema comum de referência.
tu=sample_surface(read_triangles(OUT/primary['superior']['arquivo']),2048,SEED+1);tl=sample_surface(read_triangles(OUT/primary['inferior']['arquivo']),2048,SEED+2)
origin=(tu.mean(0)+tl.mean(0))/2
entries=[]
for index in selected:
 p=dev[index]
 if p['id']=='P016':u,l=tu-origin,tl-origin;align={'R':np.eye(3).tolist(),'t':(-origin).tolist()}
 else:
  rawu=sample_surface(read_triangles(OUT/p['superior']['arquivo']),2048,SEED+1);rawl=sample_surface(read_triangles(OUT/p['inferior']['arquivo']),2048,SEED+2)
  align=normalize_anatomical(rawu,rawl,tu,tl,1.,'pca_sign');u=apply_transform(rawu,align['R'],align['t']);l=apply_transform(rawl,align['R'],align['t'])
 np.savez_compressed(OUT/'templates'/f'{p["id"]}.npz',upper=u,lower=l)
 entries.append({'id':p['id'],'aligned_to':'P016','alignment':align,'selection':'farthest-first em descritores de extensão das duas arcadas no frame orientado; só desenvolvimento'})
save_json('templates/selecao.json',entries)
save_json('plano_preteste.json',{'divisao':'mesma Etapa 3, 20/49, 17/47 conteúdos únicos','variants':['point_plane','trim_20','trim_30','posterior_40','posterior_60','multi3_rmse','multi3_medoid','multi5_rmse','multi5_medoid'],'choice_criterion':'menor média de taxas de falha >5 por paciente no desenvolvimento, empate menor média de medianas por paciente; prefere variante mais simples se empate exato','icp_max_iterations':60,'icp_distance':8,'starts':'mesmos quatro inícios anatômicos da Etapa 3','normal_neighbors':30,'bootstrap_seed':20261107,'bootstrap_patient_repetitions':10000,'gate':'não avaliar; apenas registrar 778/980 rejeições anteriores (79.39%)','posterior':'proxy geométrico por AP estimado: posterior 40% ou 60% de cada arcada, sem máscara validada da fissura'})
print('PREPARADO templates',[e['id'] for e in entries],flush=True)
