"""Verificações independentes de convenção, integridade e cobertura dos relatórios."""
from pathlib import Path
import sys,json,csv,collections
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pose_normalize import normalize_points,geodesic_deg
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from executar import planes_ransac
planar=[]
for x in range(10):
 for y in range(10):
  planar.extend([[[x,y,0],[x+1,y,0],[x,y+1,0]],[[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]])
plane=planes_ransac(np.array(planar,dtype=float))
assert plane['base_detectada_operacional']
assert np.isclose(plane['fracao_triangulos_base_candidata'],1)
assert np.isclose(plane['fracao_area_base_candidata'],1)
rng=np.random.default_rng(47)
p=rng.normal(size=(2048,3))*[20,12,5];p[:,2]+=.01*p[:,0]**2
Q=Rotation.from_euler('xyz',[127,-63,41],degrees=True).as_matrix();u=np.array([71.,-83.,29.])
r=normalize_points(p@Q.T+u,p);R=np.array(r['R']);t=np.array(r['t'])
assert geodesic_deg(R@Q)<1e-3
assert np.linalg.norm(R@u+t)<1e-5
assert r['RMSE']<1e-5
assert np.isclose(np.linalg.det(R),1)
trials=list(csv.DictReader((root/'resultados/robustez_ensaios.csv').open()))
assert len(trials)==3160
assert set(collections.Counter(r['id'] for r in trials).values())=={20}
manual=list(csv.DictReader((root/'revisao_manual.csv').open()));assert len(manual)==16
assert all((root/r['preview']).is_file() for r in manual)
assert len(list(csv.DictReader((root/'bases.csv').open())))==158
assert len(list(csv.DictReader((root/'unidades.csv').open())))==158
for entry in json.loads((root/'resultados/normalizacoes_originais.json').read_text()):
 for c in entry['candidates']:
  R=np.array(c['R']);assert np.allclose(R.T@R,np.eye(3),atol=1e-8);assert np.isclose(np.linalg.det(R),1)
assert len(json.loads((root/'validacao_integridade.json').read_text()))==158
print('OK: plano sintético RANSAC recuperado; transformação conhecida recuperada; 3.160 ensaios; 158 STL; 16 PNG; quatro rotações próprias por baseline; integridade verificada.')
