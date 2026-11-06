from common import *
from datetime import datetime,timezone
pairs={p['id']:p for p in load('pares_ids.json')};plans=load('planos/divisoes.json');targets=sorted({i for plan in plans for i in plan['bank']+[plan['primary']]});(OUT/'templates_raw').mkdir(exist_ok=True)
for identifier in targets:
 p=pairs[identifier];u=sample_surface(read_triangles(OUT/p['superior']['arquivo']),2048,SEED+1);l=sample_surface(read_triangles(OUT/p['inferior']['arquivo']),2048,SEED+2)
 np.savez_compressed(OUT/'templates_raw'/f'{identifier}.npz',upper=u,lower=l,origin=(u.mean(0)+l.mean(0))/2)
for plan in plans:
 assert len(plan['dev'])==20 and len(plan['test'])==49 and not set(plan['dev'])&set(plan['test'])
 assert set(plan['bank']+[plan['primary']])<=set(plan['dev'])
 devhash={key(pairs[i]) for i in plan['dev']};testhash={key(pairs[i]) for i in plan['test']};assert not devhash&testhash
 primary=np.load(OUT/'templates_raw'/f'{plan["primary"]}.npz');alignments={}
 for identifier in plan['bank']:
  temp=np.load(OUT/'templates_raw'/f'{identifier}.npz')
  if identifier==plan['primary']:C_R=np.eye(3);C_t=np.zeros(3)
  else:
   a=normalize_anatomical(temp['upper'],temp['lower'],primary['upper'],primary['lower'],1.,'pca_sign');C_R=np.array(a['R']);C_t=C_R@temp['origin']+np.array(a['t'])
  alignments[identifier]={'R':C_R.tolist(),'t':C_t.tolist(),'source':'native centered template to common primary frame'}
 plan['alignments']=alignments
save('planos/divisoes.json',plans)
needs={}
for plan in plans:
 for identifier in plan['test']:
  needs.setdefault(identifier,{})
  for t in plan['bank']:needs[identifier].setdefault(t,False)
  needs[identifier][plan['primary']]=True
save('planos/consultas_cache.json',needs)
paths=['protocolo.json','planos/divisoes.json','planos/consultas_cache.json','anatomical_pair.py','pca_pair.py','rigid_icp.py','scripts/common.py','scripts/cache_poses.py','scripts/congelar_planos.py','scripts/planejar.py']+[str(p.relative_to(OUT)) for p in sorted((OUT/'templates_raw').glob('*.npz'))]
save('congelamento.json',{'utc':datetime.now(timezone.utc).isoformat(),'hashes':{p:digest(OUT/p) for p in paths},'note':'protocol and all banks fixed before evaluating new query results; labels used only offline for balanced dev bank, never query inference'})
print('CONGELADO','bancos',len(plans),'templates distintos',len(targets),'consultas par-template',sum(len(v) for v in needs.values()),'consultas PCA',sum(sum(v.values()) for v in needs.values()),flush=True)
