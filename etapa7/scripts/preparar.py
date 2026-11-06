from pathlib import Path
import csv,json,hashlib,collections
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'etapa7'
def load(path):return json.loads(Path(path).read_text())
def save(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def csvsave(name,rows):
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 pairs=load(ROOT/'etapa5/pares_ids.json');labels={r['ID']:r for r in csv.DictReader((ROOT/'etapa5/rotulos_local.csv').open())};clusters=collections.defaultdict(list)
 for p in pairs:clusters[p['superior']['sha256']+'|'+p['inferior']['sha256']].append(p['id'])
 clusterby={i:sorted(ids)[0] for ids in clusters.values() for i in ids};conflicts={}
 for ids in clusters.values():
  for i in ids:conflicts[i]={'goslon':len({labels[j]['goslon'] for j in ids})>1,'grupo':len({labels[j]['grupo'] for j in ids})>1}
 outcomes=[];membership=[]
 for p in pairs:
  ID=p['id'];outcomes.append({'ID':ID,'ID_conteudo':clusterby[ID],'grupo':int(labels[ID]['grupo']),'goslon':int(labels[ID]['goslon']),'fonte_rotulo':'nome da pasta; não validado clinicamente','conflito_goslon_no_conteudo':conflicts[ID]['goslon'],'conflito_grupo_no_conteudo':conflicts[ID]['grupo']});membership.append({'ID':ID,'ID_conteudo':clusterby[ID],'participacao_no_treino':'possivel_contaminacao','fonte':'nenhum vínculo verificável entre treino do classificador e estes STL','modelo_sha256':'MODELO_AUSENTE'})
 csvsave('rotulos_avaliacao.csv',outcomes);csvsave('participacao_treino.csv',membership)
 manifest=load(ROOT/'etapa6/stl/congelamento.json');assert sha(ROOT/'etapa6/camera_config.json')==manifest['camera_sha256'];assert sha(ROOT/'etapa6/stl/modelo_normalizacao.npz')==manifest['model_sha256']
 paths=['etapa6/camera_config.json','etapa6/stl/modelo_normalizacao.npz','etapa6/stl_views.py','etapa6/render_views.py','etapa5/anatomical_pair.py','etapa5/pca_pair.py','etapa5/rigid_icp.py','etapa5/referencias/banco_original.json','etapa5/rotulos_local.csv','etapa5/divisao_original.json','etapa5/scripts/preparar.py']+[f'etapa5/clouds/{p["id"]}.npz' for p in pairs]
 save('entradas_congeladas.json',{'utc':datetime.now(timezone.utc).isoformat(),'status':'PRE_EVALUATION_INPUT_SNAPSHOT_NOT_MODEL_FREEZE','hashes':{p:sha(ROOT/p) for p in paths},'model_sha256':None,'classifier_preprocessing':None,'evaluation_executed':False})
 save('protocolo.json',{
  'status':'PREPARED_NOT_EXECUTED_MODEL_MISSING','model_training_allowed':False,'model_adjustment_allowed':False,
  'IDs':len(pairs),'patient_contents':len(clusters),'ground_truth':'rotulos_avaliacao.csv; literal folder labels, clinically unvalidated',
  'membership':'participacao_treino.csv; currently all possible contamination; pose 20/49 is not classifier membership',
  'membership_resolution':'same content used in classifier training under any alias => training for the entire content; absent or unverifiable mapping => possible contamination; never join independent ID namespaces by equal codes',
  'output_semantics':'require checkpoint class order, target meaning and preprocessing before evaluating; 3-group ordinal error is not 1–5 GOSLON error; never invent a group-to-score conversion',
  'label_conflicts':'exclude contents with contradictory target labels from primary metrics; retain raw labels and sensitivity analysis including conflicts; list exclusions. GOSLON: P021/P039 and P066/P067; group: P021/P039',
  'conditions':['sem_normalizacao','controle_PCA_ICP_combinada','regra_anatomica','multi5_rmse'],
  'normalizers':'same frozen geometry/ICP algorithms and original development templates; no re-selection on evaluation; single proper rigid transform for both arches; no scaling',
  'input_coordinate_frame':'express original mesh using fixed primary-template coordinate basis and origin; no per-patient fitting in no-normalization arm; after normalization convert to the same P016 canonical frame',
  'renderer':'etapa6 low-level render_views.py after explicit condition-specific transform; do not use the auto-normalizing stl_views wrapper in the no-normalization arm',
  'baseline':'render every method at 0 degrees; multi5 baseline can be checked against the 414 etapa6 PNGs; no classifier currently available',
  'angles_deg':[0,2,3,5,10,20],'axes':['vertical','anteroposterior','laterolateral'],'signs':[-1,1],
  'controlled_rotation':'rigidly rotate both arches around shared centroid along canonical axes; 0 degrees once per ID/method, reuse in per-axis plots without counting it as independent data',
  'n_controlled_ID_condition_cases':len(pairs)*4*(1+3*5*2),
  'swap_rate_reference':'same ID and same method at 0 degrees; optionally also report common no-normalization baseline, clearly separated',
  'realistic':'reuse exact 20 stored point-cloud perturbations per ID from etapa5/clouds; seeds, random proper Q, translations ±100 native units, independent resampling, Gaussian noise 0.15, local crop10–30%, and precomputed decimation from prior stages',
  'realistic_geometry_contract':'registration robustness: estimate pose from stored perturbed points and apply it to corresponding rigidly perturbed STL/decimated mesh for rendering; noise/crop affect registration samples, not an invented point-cloud-to-surface reconstruction. Declare displayed mesh choice before execution; do not call this surface-damage tolerance',
  'n_realistic_ID_condition_cases':len(pairs)*20*4,
  'metrics':['accuracy','macro_F1_fixed_class_universe_zero_division_0','mean_absolute_ordinal_error_in_confirmed_target_scale','prediction_swap_rate','confusion_matrix'],
  'strata':['classifier_train','classifier_not_train','possible_contamination','grupo','goslon'],
  'aggregation':'equal patient-content weights; average trial/sign contributions within ID then aliases within content; do not treat repeated trials as independent patients; conflicting target-label contents excluded from primary',
  'bootstrap':{'unit':'entire patient-content cluster, paired across methods and conditions','B':10000,'seed':20261106,'CI95':'percentile; recompute confusion/F1 each resample; no patient-level CI for strata with <2 distinct contents'},
  'tolerance':'smallest tested nonzero absolute angle with swap rate strictly above 0.05 or 0.10, separately by method/axis/stratum; both signs reported and equally pooled; no interpolation or assumption of monotonicity; if never exceeded report >20 degrees, not infinity',
  'residual_comparison':'compare per-method measured residual distribution from same realistic trials to discrete classifier tolerance; report median, IQR and quantiles, not only global median~3 degrees; no causal claim',
  'confusion_matrices':'one per method, axis, angle/sign, membership and requested label stratum; cluster weighting and raw counts separately',
  'inference':'eval/inference-only, exact model factory/graph + strict full weights + declared class/view order, RGB/resize/normalization, no training, no optimizer or BN updates; hash model before/after',
  'generation_claim':'all current IDs would be labelled possible contamination; report descriptive evaluation only, never generalization accuracy without verified membership',
  'legacy_training_image_camera_equivalence':'STL-only cameras from etapa6 are a new rendering protocol; do not attribute any future baseline gap solely to pose'
 })
 status={'status':'PENDING_TRAINED_GOSLON_MODEL','reason':'User confirmed no local trained GOSLON model path in repository; search found no suitable classifier weights','classifier_loaded':False,'model_trained_or_adjusted':False,'classification_predictions_generated':False,'classification_metrics_computed':False,'rendered_baseline_available':414,'IDs':69,'patient_contents':64,'membership_status':'all possible contamination','membership_generalization_claim_allowed':False,'required':['trained classifier weights/graph and exact architecture if separate','view/class order and image preprocessing','train-membership mapping for these STL identities if available; otherwise possible contamination remains'],'ground_truth_semantics_pending':'GOSLON scores 1–5 versus three supplied groups must match model outputs; no conversion invented','no_numeric_results_fabricated':True};save('status.json',status)
 pending=[{'condition':name,'status':'NOT_EXECUTED_MODEL_MISSING',**{metric:'PENDING' for metric in ['accuracy','macro_F1','ordinal_error','prediction_swap_rate','CI95','confusion_matrix']}} for name in ['baseline','controlled_rotation','normalized_control','normalized_anatomical','normalized_multi5','realistic','classifier_tolerance']];csvsave('resultados/metricas_pendentes.csv',pending)
 print('PREPARADO: 69 IDs, 64 conteúdos; todos possível contaminação; modelo ausente; nenhuma predição ou métrica inventada.')
if __name__=='__main__':main()
