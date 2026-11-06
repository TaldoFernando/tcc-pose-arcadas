from common import *
import ast

def main():
 checks={};frozen=load('congelamento.json');checks['frozen_hashes_unchanged']=all(digest(OUT/p)==h for p,h in frozen['hashes'].items());pairs={p['id']:p for p in load('pares_ids.json')};plans=load('planos/divisoes.json')
 splits=[]
 for p in plans:
  dev={key(pairs[i]) for i in p['dev']};test={key(pairs[i]) for i in p['test']}
  splits.append({'split':p['name'],'dev':len(p['dev']),'test':len(p['test']),'shared_content':len(dev&test),'shared_individual_arches':len({pairs[i][a]['sha256'] for i in p['dev'] for a in ['superior','inferior']}&{pairs[i][a]['sha256'] for i in p['test'] for a in ['superior','inferior']}),'templates_only_dev':set(p['bank']).issubset(p['dev']),'unique_template_contents':len({key(pairs[i]) for i in p['bank']})==len(p['bank'])})
 from datetime import datetime
 checks['clouds_created_before_freeze']=all(p.stat().st_mtime<datetime.fromisoformat(frozen['utc']).timestamp() for p in (OUT/'clouds').glob('*.npz'))
 checks['splits']=splits;assert all(s['dev']==20 and s['test']==49 and s['shared_content']==0 and s['shared_individual_arches']==0 and s['templates_only_dev'] and s['unique_template_contents'] for s in splits)
 # Leitura privada apenas para integridade e auditoria local; nenhuma string identificável é escrita.
 mapping=csv_read('privado/id_pasta_local.csv');integrity=[]
 for row in mapping:
  for arch in ['superior','inferior']:
   source=ROOT/'dados'/row[arch+'_fonte'];copied=OUT/pairs[row['ID']][arch]['arquivo'];expected=pairs[row['ID']][arch]['sha256'];integrity.append({'ID':row['ID'],'arcada':arch,'copy_matches_manifest':digest(copied)==expected,'source_unchanged':digest(source)==expected})
 csv_save('resultados/integridade.csv',integrity);checks['all_138_copies_sources_match']=len(integrity)==138 and all(r['copy_matches_manifest'] and r['source_unchanged'] for r in integrity)
 needles=set()
 for row in mapping:
  needles.add(row['pasta']);needles.add(Path(row['pasta']).name)
  for arch in ['superior','inferior']:needles.add(Path(row[arch+'_fonte']).name)
 # Nomes curtos genéricos de STL não identificam pacientes; só cadeias de origem específicas.
 needles={x for x in needles if len(x)>8 and x.lower() not in ['superior.stl','inferior.stl']};leaks=[];nfiles=0
 for p in OUT.rglob('*'):
  if not p.is_file() or 'privado' in p.relative_to(OUT).parts or p.suffix not in ['.json','.csv','.md','.log','.py','.txt']:continue
  nfiles+=1;body=p.read_text(errors='replace')
  if any(x in body for x in needles):leaks.append(str(p.relative_to(OUT)))
 checks['privacy']={'scanned_text_files':nfiles,'files_with_source_patient_strings':leaks,'mapping_excluded':True}
 # Apenas parsing estático: não importa nem chama o experimento de classificador.
 source=(OUT/'experimento_tolerancia_classificador.py').read_text();ast.parse(source);compile(source,'experimento_tolerancia_classificador.py','exec');checks['classifier']={'static_syntax_ok':True,'experiment_executed':False,'cameras':'PLACEHOLDER'}
 need=load('planos/consultas_cache.json');n=0;valid=True
 for identifier,templates in need.items():
  for tid,pca in templates.items():
   data=load(f'cache_pose/{identifier}/{tid}.json');n+=1
   for method in ['anatomica']+(['controle'] if pca else []):
    valid &= len(data[method])==21
    for r in data[method]:
     R=np.array(r['R']);valid &= bool(np.allclose(R.T@R,np.eye(3),atol=1e-6) and abs(np.linalg.det(R)-1)<1e-6 and np.isfinite(r['RMSE']))
 checks['cache']={'jobs':n,'all_poses_finite_SO3_complete':valid};checks['pass']=checks['frozen_hashes_unchanged'] and checks['all_138_copies_sources_match'] and not leaks and valid
 save('resultados/verificacoes.json',checks);assert checks['pass'],'Verification failed; see ID-only report'
 print('VERIFICADO: congelamento, divisões, SO3, cópias, privacidade e sintaxe do stub; classificador não executado.')
if __name__=='__main__':main()
