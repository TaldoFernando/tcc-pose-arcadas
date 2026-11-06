"""Retomada operacional: mesmas funções congeladas; muda apenas paralelismo CPU."""
from cache_poses import *

def main():
 frozen=load('congelamento.json')
 for path,h in frozen['hashes'].items():assert digest(OUT/path)==h
 jobs=list(load('planos/consultas_cache.json').items())
 save('execucao_cpu.json',{'workers_initial':4,'workers_resume':12,'scientific_code_changed':False,'reason':'local CPU throughput only; resume completed atomic caches; no method, bank, seed, threshold or split changed'})
 with ProcessPoolExecutor(max_workers=12,mp_context=multiprocessing.get_context('spawn'),initializer=initialize) as pool:
  futures=[pool.submit(compute,job) for job in jobs]
  for idx,future in enumerate(as_completed(futures),1):
   identifier,n,elapsed=future.result();print(idx,len(jobs),identifier,'templates',n,'seconds',round(elapsed,1),flush=True)
 print('CACHE_CONCLUIDO',flush=True)
if __name__=='__main__':main()
