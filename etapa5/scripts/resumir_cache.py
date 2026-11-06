"""Converte inferência em métricas, sem fornecer rótulos à normalização."""
from common import *
from collections import defaultdict

def evaluate_plan(plan):
 output=[];bases={};primary=plan['primary']
 for identifier in plan['test']:
  clouds=np.load(OUT/'clouds'/f'{identifier}.npz');cache={t:json.loads((OUT/'cache_pose'/identifier/f'{t}.json').read_text()) for t in plan['bank']}
  methods={m:[] for m in ['controle','anatomica','multi5_rmse']}
  for index in range(21):
   for method in ['controle','anatomica']:
    r=cache[primary][method][index];methods[method].append({**r,'template_ID':primary})
   tid=min(plan['bank'],key=lambda t:cache[t]['anatomica'][index]['RMSE']);r=cache[tid]['anatomica'][index];align=plan['alignments'][tid];C=np.array(align['R']);ct=np.array(align['t'])
   methods['multi5_rmse'].append({**r,'R':(C@np.array(r['R'])).tolist(),'t':(C@np.array(r['t'])+ct).tolist(),'template_ID':tid})
  bases[identifier]={m:rows[0] for m,rows in methods.items()}
  target=np.load(OUT/'templates_raw'/f'{primary}.npz');F,_=anatomical_frame(target['upper'],target['lower'],1.,'pca_sign')
  from scipy.spatial.transform import Rotation
  for method,rows in methods.items():
   R0=np.array(rows[0]['R']);t0=np.array(rows[0]['t'])
   for k,r in enumerate(rows[1:]):
    R=np.array(r['R']);t=np.array(r['t']);Q=clouds[f'Q{k:02d}'];shift=clouds[f't{k:02d}'];D=R@Q@R0.T;v=np.rad2deg(Rotation.from_matrix(F.T@D@F).as_rotvec())
    output.append({'ID':identifier,'method':method,'trial':k+1,'error_deg':geodesic_deg(D),'vertical_deg':float(v[2]),'RMSE':r['RMSE'],'icp_rmse':r['icp_rmse'],'template_ID':r['template_ID'],'translation_error':float(np.linalg.norm(R@shift+t-t0))})
 return output,bases

def main():
 plans=load('planos/divisoes.json');all_metrics=[]
 for plan in plans:
  rows,bases=evaluate_plan(plan);csv_save('resultados/ensaios_'+plan['name']+'.csv',rows);save('resultados/baselines_'+plan['name']+'.json',bases)
  all_metrics.append({'plan':plan['name'],'rows':len(rows)})
 save('resultados/cobertura.json',all_metrics)
 print('RESUMOS DE INFERENCIA CONCLUIDOS',len(plans))
if __name__=='__main__':main()
