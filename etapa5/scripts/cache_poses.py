"""Inferência pura: IDs, nuvens e geometria dos templates. Nunca abre rótulos."""
from common import *
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing,time
_TEMPLATES={}

def initialize():
 global _TEMPLATES
 for path in (OUT/'templates_raw').glob('P*.npz'):
  d=np.load(path);_TEMPLATES[path.stem]=(d['upper'],d['lower'])

def compact(r):return {'R':r['R'],'t':r['t'],'RMSE':r['RMSE'],'icp_rmse':r.get('icp_rmse',r.get('icp_inlier_rmse')),'fitness':r['fitness'],'candidate':r['candidate']}

def compute(job):
 identifier,need=job;start=time.time();cloud=np.load(OUT/'clouds'/f'{identifier}.npz');queries=[(cloud['superior_base'],cloud['inferior_base'])]+[(cloud[f'superior{k:02d}'],cloud[f'inferior{k:02d}']) for k in range(20)]
 completed=0
 for tid,need_pca in need.items():
  path=OUT/'cache_pose'/identifier/f'{tid}.json';path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():
   existing=json.loads(path.read_text())
   if len(existing['anatomica'])==21 and (not need_pca or len(existing.get('controle',[]))==21):continue
  tu,tl=_TEMPLATES[tid];results={'ID':identifier,'template_ID':tid,'anatomica':[],'controle':[]}
  for u,l in queries:
   results['anatomica'].append(compact(normalize_anatomical(u,l,tu,tl,1.,'pca_sign')))
   if need_pca:results['controle'].append(compact(normalize_pair_points(u,l,tu,tl,'combinada')))
  temp=path.with_suffix('.tmp');temp.write_text(json.dumps(results,separators=(',',':')));temp.replace(path);completed+=1
 return identifier,completed,time.time()-start

def main():
 frozen=load('congelamento.json')
 for path,h in frozen['hashes'].items():assert digest(OUT/path)==h,'Frozen code/bank changed'
 jobs=list(load('planos/consultas_cache.json').items())
 with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),initializer=initialize) as pool:
  futures=[pool.submit(compute,job) for job in jobs]
  for idx,future in enumerate(as_completed(futures),1):
   identifier,n,elapsed=future.result();print(idx,len(jobs),identifier,'templates',n,'seconds',round(elapsed,1),flush=True)
 print('CACHE_CONCLUIDO',flush=True)
if __name__=='__main__':main()
