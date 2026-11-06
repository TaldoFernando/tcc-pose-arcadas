from common import *
from replay import *
from anatomical_pair import normalize_anatomical
import argparse,time

def main(subset):
    split=load_json('divisao.json');rules=load_json('regra.json');ids=split['desenvolvimento' if subset=='dev' else 'teste'];pairs=[p for p in load_json('pares.json') if p['id'] in ids]
    if subset=='test':
        frozen=load_json('congelamento.json')
        for path,expected in frozen['hashes'].items():assert digest(OUT/path)==expected,'Código/regra alterado após congelamento: '+path
    folder='desenvolvimento' if subset=='dev' else 'teste'
    tu=sample_surface(read_triangles(OUT/'templates/superior.stl'),2048,SEED+1);tl=sample_surface(read_triangles(OUT/'templates/inferior.stl'),2048,SEED+2)
    baselines=[];trials=[]
    if (OUT/folder/'baselines.json').exists():baselines=load_json(folder+'/baselines.json');trials=load_json(folder+'/ensaios.json')
    done={r['id'] for r in baselines}
    for idx,p in enumerate(pairs):
        if p['id'] in done:continue
        start=time.time();u,l=baseline_points(p)
        original={'anatomica':normalize_anatomical(u,l,tu,tl,rules['weight'],rules['vertical_mode']),'pca_controle':normalize_pair_points(u,l,tu,tl,'combinada')}
        b={'id':p['id'],'methods':original}
        maxerrors={m:[] for m in original}
        for k in range(20):
            (pu,pl),Q,shift,seed,meta=perturb(p,k)
            estimates={'anatomica':normalize_anatomical(pu,pl,tu,tl,rules['weight'],rules['vertical_mode']),'pca_controle':normalize_pair_points(pu,pl,tu,tl,'combinada')}
            for method,r in estimates.items():
                R=np.array(r['R']);t=np.array(r['t']);R0=np.array(original[method]['R']);t0=np.array(original[method]['t'])
                error=geodesic_deg(R@Q@R0.T);maxerrors[method].append(error)
                trials.append({'id':p['id'],'method':method,'trial':k+1,'seed':seed,'error_deg':error,'translation_error':float(np.linalg.norm(R@shift+t-t0)),'failed':error>5,'Q':Q.tolist(),'u':shift.tolist(),'meta':meta,'result':r})
        baselines.append(b);save_json(folder+'/baselines.json',baselines);save_json(folder+'/ensaios.json',trials)
        print(subset,idx+1,len(pairs),p['id'],{m:round(max(v),3) for m,v in maxerrors.items()},f'{time.time()-start:.1f}s',flush=True)
    print(subset.upper()+'_CONCLUIDO',flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('subset',choices=['dev','test']);args=parser.parse_args();main(args.subset)
