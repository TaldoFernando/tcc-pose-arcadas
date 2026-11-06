from common import *
from datetime import datetime,timezone
from collections import defaultdict
trials=load_json('desenvolvimento/ensaios.json');pairs={p['id']:p for p in load_json('pares.json')};split=load_json('divisao.json')
assert {r['id'] for r in trials}==set(split['desenvolvimento'])
methods=sorted({r['method'] for r in trials});metrics={}
for m in methods:
 groups=defaultdict(list)
 for identifier in split['desenvolvimento']:
  v=np.array([r['error_deg'] for r in trials if r['id']==identifier and r['method']==m]);assert len(v)==20
  p=pairs[identifier];key=(p['superior']['sha256'],p['inferior']['sha256']);groups[key].append((np.mean(v>5),np.median(v)))
 arr=np.array([np.mean(values,axis=0) for values in groups.values()]);metrics[m]={'mean_patient_failure5_content_balanced':float(arr[:,0].mean()),'mean_patient_median_content_balanced':float(arr[:,1].mean()),'n_patient_ids':20,'n_unique_contents':len(groups)}
def choose(options):return min(options,key=lambda m:(metrics[m]['mean_patient_failure5_content_balanced'],metrics[m]['mean_patient_median_content_balanced'],m))
selected=['point_plane',choose(['trim_20','trim_30']),choose(['posterior_40','posterior_60']),choose(['multi3_rmse','multi3_medoid','multi5_rmse','multi5_medoid'])]
save_json('desenvolvimento/comparacao_configs.json',metrics)
save_json('escolhas.json',{'selected':selected,'criterion':'mean failure5 by development patient-content group; tie mean of patient medians','all_metrics_dev':metrics,'gate':'não reajustada nem aplicada'})
paths=['refinements.py','rigid_icp.py','anatomical_pair.py','pca_pair.py','scripts/common.py','scripts/replay.py','scripts/executar.py','scripts/preparar.py','scripts/congelar.py','divisao.json','escolhas.json','plano_preteste.json','templates/selecao.json']+[str(p.relative_to(OUT)) for p in sorted((OUT/'templates').glob('*.npz'))]
save_json('congelamento.json',{'utc':datetime.now(timezone.utc).isoformat(),'hashes':{p:digest(OUT/p) for p in paths},'statement':'Escolhas fixadas somente no desenvolvimento; teste ainda não executado nesta etapa.'})
print('CONGELADO',selected,metrics,flush=True)
