"""Auditoria independente dos artefatos do modelo substituto, sem treinar/ajustar."""
from pathlib import Path
import json,csv,collections,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa7b'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 checks={};freeze=load(OUT/'congelamento.json');checks['frozen_hashes_unchanged']=all(sha(ROOT/p)==h for p,h in freeze['files'].items())
 folds=list(csv.DictReader((OUT/'conteudos_folds.csv').open()));bycontent=collections.defaultdict(set)
 for r in folds:bycontent[r['ID_conteudo']].add(r['fold'])
 checks['aliases_never_cross_folds']=all(len(s)==1 for s in bycontent.values())
 units=load(OUT/'unidades.json');checks['unique_content_count_63']=len(units)==63;checks['conflicting_group_content_excluded']=not any(u['ID'] in ['P021','P039'] for u in units)
 checks['five_folds']=set(u['fold'] for u in units)==set(range(5))
 checks['copied_STL_hashes_unchanged']=all(sha(ROOT/'etapa5'/r['arquivo'])==r['sha256'] for r in load(ROOT/'etapa5/manifesto_ids.json'))
 pixel_repeats=[];features=[];cases=0;blank=collections.Counter();clip=collections.Counter();residuals=collections.defaultdict(list)
 for u in units:
  z=np.load(OUT/'features'/f"{u['ID']}.npz");rr=json.loads(str(z['records']));features.append(bool(np.isfinite(z['features']).all() and np.isfinite(z['descriptors']).all() and z['features'].shape==(213,6,576)));cases+=len(rr)
  counts=collections.Counter((r['condition'],r['method']) for r in rr)
  assert counts=={('canonical','nenhuma'):1,('augmentation','nenhuma'):12,('rotation','nenhuma'):30,('rotation','controle'):30,('rotation','anatomica'):30,('rotation','multi5_rmse'):30,('realistic','nenhuma'):20,('realistic','controle'):20,('realistic','anatomica'):20,('realistic','multi5_rmse'):20}
  for r in rr:
   blank[(r['condition'],r['method'])]+=r['empty_views']
   if r['condition']=='rotation' and r['method']!='nenhuma':residuals[r['method']].append(r['pose_error_deg'])
 checks['all_features_finite_expected_shape']=all(features);checks['all_conditions_complete']=cases==63*213
 if (OUT/'predicoes_oof.csv').exists():
  rows=list(csv.DictReader((OUT/'predicoes_oof.csv').open()));checks['OOF_prediction_count']=len(rows)==63*201*5
  byid={u['ID']:u for u in units};checks['test_fold_matches_patient']=all(int(r['fold'])==byid[r['ID']]['fold'] for r in rows)
  logs=load(OUT/'treinamento.json');checks['no_test_used_for_selection']=len(logs)==15 and all(not r['test_used_for_selection'] and r['epochs']==80 for r in logs)
  import torch
  checkpoint_ok=[]
  for path in sorted((OUT/'checkpoints').glob('*.pt')):
   c=torch.load(path,map_location='cpu',weights_only=True);checkpoint_ok.append(not(set(c['train_IDs'])&set(c['test_IDs'])) and all(byid[i]['fold']!=c['fold'] for i in c['train_IDs']) and all(byid[i]['fold']==c['fold'] for i in c['test_IDs']))
  checks['checkpoint_train_test_disjoint']=len(checkpoint_ok)==15 and all(checkpoint_ok)
  # Recalcula uma métrica agregada diretamente das predições, sem usar relatório.
  rr=[r for r in rows if r['model']=='substituto_canonico' and r['condition']=='canonical'];acc=np.mean([int(r['predicao'])==int(r['grupo_real']) for r in rr]);reported=next(r for r in csv.DictReader((OUT/'metricas_IC95.csv').open()) if r['modelo']=='substituto_canonico' and r['condicao']=='canonical');checks['accuracy_independently_recomputed']=abs(acc-float(reported['acuracia']))<1e-12
 checks={k:bool(v) for k,v in checks.items()};times=[load(p) for p in (OUT/'features').glob('*.json')];result={'rotulo':'MODELO SUBSTITUTO','checks':checks,'all_checks_passed':all(checks.values()),'cases':cases,'images_rendered':cases*6,'blank_views':{'|'.join(k):v for k,v in blank.items()},'controlled_rotation_max_residual_deg':{k:max(v) for k,v in residuals.items()},'timing_median_seconds_per_content':{k:float(np.median([t[k] for t in times])) for k in ['render_seconds','fit_seconds','total_seconds']}}
 (OUT/'verificacoes.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['all_checks_passed']
if __name__=='__main__':main()
