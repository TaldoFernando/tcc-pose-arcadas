from common import *
from replay import *
from refinements import Target,refine,aggregate_multi
import argparse,time

def estimate(u,l,targets,configs):
    results={}
    for mode in configs:
        if not mode.startswith('multi'):results[mode]=refine(u,l,targets[0],mode)
    multi=[mode for mode in configs if mode.startswith('multi')]
    if multi:
        n=max(int(mode.split('_')[0][5:]) for mode in multi);individual=[refine(u,l,t,'point_point') for t in targets[:n]]
        for mode in multi:results[mode]=aggregate_multi(individual,int(mode.split('_')[0][5:]),mode.split('_')[1])
    return results

def load_targets():
    entries=load_json('templates/selecao.json');targets=[]
    for entry in entries:
        d=np.load(OUT/'templates'/f'{entry["id"]}.npz');targets.append(Target(d['upper'],d['lower']))
    return targets

_WORK_TARGETS=None
_WORK_CONFIGS=None

def initialize_worker(configs):
    global _WORK_TARGETS,_WORK_CONFIGS
    _WORK_TARGETS=load_targets();_WORK_CONFIGS=configs

def compute_patient(p,configs,targets):
    start=time.time();u,l=baseline_points(p);baseline=estimate(u,l,targets,configs);output=[]
    for k in range(20):
        (pu,pl),Q,shift,seed,meta=perturb(p,k);estimates=estimate(pu,pl,targets,configs)
        for method,r in estimates.items():
            R=np.array(r['R']);R0=np.array(baseline[method]['R']);D=R@Q@R0.T;error=180. if r.get('invalid',False) or baseline[method].get('invalid',False) else geodesic_deg(D)
            output.append({'id':p['id'],'method':method,'trial':k+1,'seed':seed,'error_deg':error,'failed':error>5,'Q':Q.tolist(),'u':shift.tolist(),'error_rotation':D.tolist(),'result':r})
    return {'id':p['id'],'methods':baseline},output,time.time()-start

def worker(p):return compute_patient(p,_WORK_CONFIGS,_WORK_TARGETS)

def main(subset,workers=1):
    split=load_json('divisao.json');folder='desenvolvimento' if subset=='dev' else 'teste';pairs=[p for p in load_json('pares.json') if p['id'] in split['desenvolvimento' if subset=='dev' else 'teste']]
    if subset=='dev':configs=load_json('plano_preteste.json')['variants']
    else:
        frozen=load_json('congelamento.json')
        for path,h in frozen['hashes'].items():assert digest(OUT/path)==h,'Alterado após congelamento: '+path
        configs=load_json('escolhas.json')['selected']
    output=[];bases=[]
    if (OUT/folder/'ensaios.json').exists():output=load_json(folder+'/ensaios.json');bases=load_json(folder+'/baselines.json')
    done={r['id'] for r in bases};pending=[p for p in pairs if p['id'] not in done]
    if workers==1:
        targets=load_targets();iterator=(compute_patient(p,configs,targets) for p in pending);pool=None
    else:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor,as_completed
        pool=ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize_worker,initargs=(configs,))
        futures=[pool.submit(worker,p) for p in pending];iterator=(future.result() for future in as_completed(futures))
    for baseline,new_rows,elapsed in iterator:
        bases.append(baseline);output.extend(new_rows);save_json(folder+'/ensaios.json',output);save_json(folder+'/baselines.json',bases)
        print(subset,len(bases),len(pairs),baseline['id'],f'{elapsed:.1f}s',flush=True)
    if pool is not None:pool.shutdown()
    print(subset.upper()+'_CONCLUIDO',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('subset',choices=['dev','test']);p.add_argument('--workers',type=int,default=1);args=p.parse_args();main(args.subset,args.workers)
