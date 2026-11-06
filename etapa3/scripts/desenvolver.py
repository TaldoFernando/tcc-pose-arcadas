from common import *
from replay import *
from anatomical_pair import anatomical_frame
import shutil
pairs=load_json('pares.json');split=load_json('divisao.json');dev=[p for p in pairs if p['id'] in split['desenvolvimento']]
results=[]
for mode,weight in itertools.product(['centroid','pca_sign'],[0.,.5,1.]):
 errors=[]
 for p in dev:
  u,l=baseline_points(p);F0,_=anatomical_frame(u,l,weight,mode)
  for k in range(20):
   (pu,pl),Q,t,seed,meta=perturb(p,k);F1,info=anatomical_frame(pu,pl,weight,mode)
   err=geodesic_deg(F1.T@Q@F0);errors.append(err)
 results.append({'weight':weight,'vertical_mode':mode,'falhas_maior90':float(np.mean(np.array(errors)>90)),'mediana_erro_inicial':float(np.median(errors)),'media':float(np.mean(errors))})
 print(results[-1],flush=True)
best=min(results,key=lambda r:(r['falhas_maior90'],r['mediana_erro_inicial']))
# Template apenas do desenvolvimento, medóide de orientação PCA superior (deduplicado).
seen=set();eligible=[]
for p in dev:
 h=(p['superior']['sha256'],p['inferior']['sha256'])
 if h not in seen:eligible.append(p);seen.add(h)
D=np.zeros((len(eligible),len(eligible)))
for i,j in itertools.combinations(range(len(eligible)),2):D[i,j]=D[j,i]=angular_axes(np.array(eligible[i]['superior_axes']),np.array(eligible[j]['superior_axes']))
template=eligible[int(np.argmin(D.sum(1)))]
(OUT/'templates').mkdir(exist_ok=True)
for a in ['superior','inferior']:shutil.copy2(OUT/template[a]['arquivo'],OUT/'templates'/f'{a}.stl')
save_json('desenvolvimento/comparacao_regras.json',results)
save_json('regra.json',{'weight':best['weight'],'vertical_mode':best['vertical_mode'],'template_id':template['id'],'template_method':'medoide PCA superior restrito ao desenvolvimento, sem duplicatas','seed_split':20261106,'samples':2048,'noise_sigma':.15,'icp_iterations':60,'jitter_deg':10,'failure_threshold_deg':5,'quality_features':['icp_rmse','agreement_max_deg'],'gate_oof_target_sensitivity':.90,'rule_selection':'menor taxa de inversão >90 graus do frame no desenvolvimento; desempate por mediana angular inicial','diagnostic_near_initial_deg':30})
print('REGRA_ESCOLHIDA',best,'TEMPLATE',template['id'],flush=True)
