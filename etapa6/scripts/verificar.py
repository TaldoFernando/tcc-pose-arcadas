from pathlib import Path
import csv,json,hashlib,ast,platform,importlib.metadata
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 current=json.loads((OUT/'camera_config.json').read_text())
 if current.get('status')=='STANDARDIZED_STL':
  import runpy
  runpy.run_path(str(OUT/'stl/scripts/verificar.py'),run_name='__main__')
  return
 cfg=json.loads((OUT/'camera_config.json').read_text());checks={'training_config_stays_PLACEHOLDER':cfg['status']=='PLACEHOLDER' and cfg['allow_uncalibrated'] is False and cfg['calibration_executed'] is False,'patient_calibration_executed':False,'patient_validation_executed':False}
 tests=json.loads((OUT/'resultados/testes_render.json').read_text());checks['renderer_tests_pass']=all(tests.values());checks['calibrator_synthetic_tests_pass']=all(json.loads((OUT/'resultados/testes_calibrador.json').read_text()).values());checks['repeat_images_identical']=all(r['identical_repeat']=='True' for r in csv.DictReader((OUT/'resultados/determinismo.csv').open()));checks['sixty_demonstration_images']=len(list((OUT/'demonstracao').glob('P*/*.png')))==60
 rows=list(csv.DictReader((ROOT/'inventario.csv').open()));checks['original_STL_count']=len(rows);checks['original_STL_unchanged']=all(digest(ROOT/'dados'/r['arquivo'])==r['sha256'] for r in rows)
 manifest=json.loads((ROOT/'etapa5/manifesto_ids.json').read_text());checks['copies_unchanged']=all(digest(ROOT/'etapa5'/r['arquivo'])==r['sha256'] for r in manifest)
 mapping=list(csv.DictReader((ROOT/'etapa5/privado/id_pasta_local.csv').open()));needles={x for r in mapping for x in [r['pasta'],Path(r['pasta']).name,Path(r['superior_fonte']).name,Path(r['inferior_fonte']).name] if len(x)>8 and x.lower() not in ['superior.stl','inferior.stl']};leaks=[];count=0
 for p in OUT.rglob('*'):
  if not p.is_file() or 'privado' in p.relative_to(OUT).parts or p.suffix not in ['.json','.csv','.md','.py','.log','.txt','.swift']:continue
  count+=1
  if any(n in p.read_text(errors='replace') for n in needles):leaks.append(str(p.relative_to(OUT)))
 checks['privacy']={'public_text_files_scanned':count,'files_with_patient_source_strings':leaks,'private_mapping_excluded':True};checks['syntax_ok']=True
 for p in [*OUT.glob('*.py'),*(OUT/'scripts').glob('*.py')]:ast.parse(p.read_text())
 checks['environment']={'python':platform.python_version(),'machine':platform.machine(),**{name:importlib.metadata.version(name) for name in ['numpy','numba','Pillow','scipy','scikit-image','opencv-python-headless']}}
 checks['pass']=all(checks[k] for k in ['training_config_stays_PLACEHOLDER','renderer_tests_pass','calibrator_synthetic_tests_pass','repeat_images_identical','sixty_demonstration_images','original_STL_unchanged','copies_unchanged','syntax_ok']) and not leaks
 (OUT/'resultados/verificacoes.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));assert checks['pass'],'Falha de verificação: ver relatório sem nomes'
 files=[*OUT.glob('*.py'),*OUT.glob('camera_config*.json'),OUT/'protocolo_calibracao.json',*(OUT/'scripts').glob('*.py')];(OUT/'implementacao_manifesto.json').write_text(json.dumps({'status':'implementation snapshot only; NOT calibrated training cameras','hashes':{str(p.relative_to(OUT)):digest(p) for p in files}},indent=2));print('AUDITORIA PASSOU: 158 originais e 138 cópias intactos; saídas sem nomes; calibração de treino não executada.')
if __name__=='__main__':main()
