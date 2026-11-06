"""API STL→seis vistas, sem receber grupo/rótulo como entrada geométrica."""
from pathlib import Path
from functools import lru_cache
import os,sys,json
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from render_views import read_stl,render_views as render_canonical,prepare_mesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'etapa5'))
from anatomical_pair import normalize_anatomical
from rigid_icp import sample_surface

@lru_cache(maxsize=4)
def _model(path):
    with np.load(path,allow_pickle=False) as data:return {k:data[k].copy() for k in data.files}

def load_config(camera_config):
    if isinstance(camera_config,(str,Path)):
        path=Path(camera_config).resolve();return json.loads(path.read_text()),path.parent
    return camera_config,Path(__file__).resolve().parent

def normalize_pair(mesh,camera_config):
    """Um único R/t para o par; sem espelhamento, escala ou ajuste por grupo."""
    cfg,base=load_config(camera_config);model=_model(str((base/cfg['normalization_model']).resolve()));tri={a:read_stl(mesh[a]) if isinstance(mesh[a],(str,Path)) else np.asarray(mesh[a],float) for a in ['superior','inferior']}
    points={a:sample_surface(tri[a],2048,20261105+11+j) for j,a in enumerate(['superior','inferior'])};fits=[]
    for k,tid in enumerate(model['IDs']):
        fit=normalize_anatomical(points['superior'],points['inferior'],model[f'upper_{k}'],model[f'lower_{k}'],1.,'pca_sign');C=model[f'C_R_{k}'];ct=model[f'C_t_{k}'];R=C@np.array(fit['R']);t=C@np.array(fit['t'])+ct;fits.append((float(fit['RMSE']),k,R,t))
    rmse,k,R,t=min(fits,key=lambda item:(item[0],item[1]));F=model['canonical_F'];R=F.T@R;t=F.T@t
    normalized={a:v@R.T+t for a,v in tri.items()};return normalized,{'R':R.tolist(),'t':t.tolist(),'RMSE':rmse,'template_ID':str(model['IDs'][k]),'proper_rotation':bool(np.linalg.det(R)>0),'method':'multi5_rmse_original_dev_bank','scale_applied':1.0}

def render_views(mesh,camera_config):
    """Recebe par STL original (cópias locais), normaliza e retorna seis RGB uint8."""
    cfg,_=load_config(camera_config)
    if cfg.get('status')!='STANDARDIZED_STL':raise ValueError('Esta API exige o protocolo STANDARDIZED_STL')
    normalized,_=normalize_pair(mesh,camera_config)
    return render_canonical(prepare_mesh(normalized,cfg['appearance'].get('shading','smooth')),cfg)
