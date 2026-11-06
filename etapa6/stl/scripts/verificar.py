from pathlib import Path
import os,sys,json,csv,hashlib,copy,re,ast
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'etapa6';OUT=BASE/'stl';sys.path.insert(0,str(BASE))
from stl_views import render_views,normalize_pair
from render_views import read_stl

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 cfg=json.loads((BASE/'camera_config.json').read_text());frozen=json.loads((OUT/'congelamento.json').read_text());checks={'scope':'STL only; groups organize outputs, never control normalization/cameras','camera_frozen_hash_matches':sha(BASE/'camera_config.json')==frozen['camera_sha256'],'model_frozen_hash_matches':sha(OUT/'modelo_normalizacao.npz')==frozen['model_sha256'],'frozen_code_matches':all(sha(BASE/p)==h for p,h in frozen['code_sha256'].items())};pairs={p['id']:p for p in json.loads((ROOT/'etapa5/pares_ids.json').read_text())};fits=json.loads((OUT/'transformacoes.json').read_text());checks['all_69_rigid_proper']=len(fits)==69 and all(np.allclose(np.array(r['R']).T@np.array(r['R']),np.eye(3),atol=1e-6) and abs(np.linalg.det(r['R'])-1)<1e-6 and r['scale_applied']==1 for r in fits)
 dev=set(cfg['camera_fit_IDs']);test=set(cfg['heldout_IDs']);key=lambda i:pairs[i]['superior']['sha256']+'|'+pairs[i]['inferior']['sha256'];checks['development20_test49_no_content_leak']=len(dev)==20 and len(test)==49 and not ({key(i) for i in dev}&{key(i) for i in test})
 images=list(csv.DictReader((OUT/'manifesto_imagens.csv').open()));checks['all_414_PNG_hashes_match']=len(images)==414 and all(sha(BASE/r['arquivo'])==r['sha256_png'] for r in images);checks['all_512_RGB']=all(Image.open(BASE/r['arquivo']).size==(512,512) and Image.open(BASE/r['arquivo']).mode=='RGB' for r in images)
 labels={r['ID']:int(r['grupo']) for r in csv.DictReader((OUT/'rotulos.csv').open())};repeated=[]
 for ID in ['P003','P037','P047']:
  mesh={a:read_stl(ROOT/'etapa5'/pairs[ID][a]['arquivo']) for a in ['superior','inferior']};before={a:hashlib.sha256(v.tobytes()).hexdigest() for a,v in mesh.items()};render=render_views(mesh,BASE/'camera_config.json')
  for view,im in render.items():
   expected=next(r for r in images if r['ID']==ID and r['view']==view);repeated.append({'ID':ID,'view':view,'identical_to_saved':hashlib.sha256(im.tobytes()).hexdigest()==expected['sha256_pixels']})
  assert all(before[a]==hashlib.sha256(v.tobytes()).hexdigest() for a,v in mesh.items())
  if ID=='P003':
   altered=copy.deepcopy(cfg);altered['grupo']=999;again=render_views({**mesh,'grupo':999},altered);checks['changing_group_does_not_change_pixels']=all(np.array_equal(render[v],again[v]) for v in render)
 checks['18_repeat_images_identical']=all(r['identical_to_saved'] for r in repeated);(OUT/'determinismo.json').write_text(json.dumps(repeated,indent=2))
 inv=list(csv.DictReader((ROOT/'inventario.csv').open()));checks['all_158_original_STL_intact']=all(sha(ROOT/'dados'/r['arquivo'])==r['sha256'] for r in inv);checks['all_138_working_copies_intact']=all(sha(ROOT/'etapa5'/p[a]['arquivo'])==p[a]['sha256'] for p in pairs.values() for a in ['superior','inferior'])
 mapping=list(csv.DictReader((ROOT/'etapa5/privado/id_pasta_local.csv').open()));selected={r[a+'_fonte'] for r in mapping for a in ['superior','inferior']};others=[{'ID_arquivo':f'STL{k:03d}','categoria':r['arcada'],'status':'fora dos 69 pares inequívocos; não inventar arcada ou pareamento'} for k,r in enumerate(inv,1) if r['arquivo'] not in selected]
 with (OUT/'arquivos_fora_dos_pares.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(others[0]));w.writeheader();w.writerows(others)
 needles={x for r in mapping for x in [r['pasta'],Path(r['pasta']).name,Path(r['superior_fonte']).name,Path(r['inferior_fonte']).name] if len(x)>8 and x.lower() not in ['superior.stl','inferior.stl']};leaks=[]
 for p in BASE.rglob('*'):
  if p.is_file() and 'privado' not in p.relative_to(BASE).parts and p.suffix in ['.py','.md','.csv','.json','.log','.txt'] and any(s in p.read_text(errors='replace') for s in needles):leaks.append(str(p.relative_to(BASE)))
 checks['privacy_files_with_patient_strings']=leaks;checks['public_outputs_only_IDs']=not leaks
 checks['all_python_syntax_ok']=True
 for p in [BASE/'render_views.py',BASE/'stl_views.py',*(OUT/'scripts').glob('*.py')]:ast.parse(p.read_text())
 checks['pass']=all(v for k,v in checks.items() if isinstance(v,bool));(OUT/'verificacoes.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));assert checks['pass'],'Verificação falhou, ver relatório com IDs';print('VERIFICADO: 414 imagens, repetição idêntica, grupo sem efeito geométrico, originais intactos e saídas com IDs.')
if __name__=='__main__':main()
