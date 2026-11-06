"""Normalização congelada multi5_rmse: sem escala, espelhamento ou gravação de STL."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[name]='1'
from pathlib import Path
import sys,json,hashlib
from functools import lru_cache
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'etapa5'),str(ROOT/'etapa6')]
from anatomical_pair import normalize_anatomical
from rigid_icp import sample_surface
def load_config():return json.loads((BASE/'config.json').read_text())
def verify_frozen():
 manifest=json.loads((BASE/'congelamento.json').read_text())
 for relative,digest in manifest['source_files'].items():
  if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:raise RuntimeError('Dependência de normalização congelada alterada.')
 if hashlib.sha256((BASE/'camera_config.json').read_bytes()).hexdigest()!=manifest['camera_copy_sha256']:raise RuntimeError('Câmeras próprias alteradas sem novo versionamento.')
 if hashlib.sha256((BASE/'config.json').read_bytes()).hexdigest()!=manifest['config_sha256']:raise RuntimeError('Configuração alterada sem novo versionamento.')
@lru_cache(maxsize=1)
def _bank():
 with np.load(ROOT/'etapa6/stl/modelo_normalizacao.npz',allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
def rotation_angle(R):return float(np.degrees(np.arccos(np.clip((np.trace(R)-1)/2,-1,1))))
def _mesh(value):
 a=np.asarray(value,dtype=np.float64)
 if a.ndim!=3 or a.shape[1:]!=(3,3) or not len(a) or not np.isfinite(a).all():raise ValueError('Arcada inválida: triângulos finitos Nx3x3 são obrigatórios.')
 areas=np.linalg.norm(np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]),axis=1)
 if not np.isfinite(areas.sum()) or areas.sum()<=1e-12:raise ValueError('Malha sem superfície amostrável.')
 return a
def normalize_pair(superior,inferior):
 """Recebe arrays Nx3x3; retorna (malhas novas, R/t/RMSE/flags serializáveis).

 Mantém exatamente amostragem, banco, regra anatômica, ICP e desempate anteriores.
 Indicadores adicionais são consultivos: não mudam a seleção nem filtram a entrada.
 """
 verify_frozen();cfg=load_config();bank=_bank();tri={'superior':_mesh(superior),'inferior':_mesh(inferior)};points={a:sample_surface(tri[a],2048,20261105+11+j) for j,a in enumerate(['superior','inferior'])};fits=[]
 for k,identifier in enumerate(bank['IDs']):
  fit=normalize_anatomical(points['superior'],points['inferior'],bank[f'upper_{k}'],bank[f'lower_{k}'],1.,'pca_sign');R=bank['canonical_F'].T@bank[f'C_R_{k}']@np.array(fit['R']);t=bank['canonical_F'].T@(bank[f'C_R_{k}']@np.array(fit['t'])+bank[f'C_t_{k}']);fits.append({'k':k,'template_ID':str(identifier),'R':R,'t':t,'fit':fit})
 best=min(fits,key=lambda f:(float(f['fit']['RMSE']),f['k']));R=best['R'];t=best['t'];fit=best['fit'];det=float(np.linalg.det(R));orth=float(np.linalg.norm(R.T@R-np.eye(3)))
 if abs(det-1)>1e-6 or orth>1e-6 or not np.isfinite(R).all() or not np.isfinite(t).all():raise RuntimeError('Transformação rígida inválida.')
 q=cfg['quality'];flags=[]
 def flag(code,attention,message,value=None):flags.append({'code':code,'level':'attention' if attention else 'ok','message':message,'value':value,'advisory':True})
 flag('proper_rotation',False,'Rotação própria em SO(3), sem espelhamento.',det)
 flag('registration_rmse',fit['RMSE']>q['rmse_warn_mm'],'RMSE simétrico de superfície; não é erro anatômico nem confiança de classificação.',float(fit['RMSE']))
 flag('candidate_agreement',fit['agreement_max_deg']>q['candidate_disagreement_warn_deg'],'Concordância entre inicializações do template escolhido; alerta consultivo.',float(fit['agreement_max_deg']))
 flag('surface_support',fit['fitness']<q['fitness_warn'],'Suporte de correspondências do ICP com corte já congelado.',float(fit['fitness']))
 ranked=sorted(fits,key=lambda f:(float(f['fit']['RMSE']),f['k']));second=ranked[1];gap=float((second['fit']['RMSE']-fit['RMSE'])/max(fit['RMSE'],1e-12));disagreement=rotation_angle(second['R']@R.T)
 flag('competing_templates',gap<q['template_relative_gap_warn'] and disagreement>q['candidate_disagreement_warn_deg'],'Templates com RMSE próximo e orientações discordantes merecem revisão.',{'relative_rmse_gap':gap,'angle_deg':disagreement})
 dimensions={}
 for a,v in tri.items():
  extent=np.ptp(v.reshape(-1,3),axis=0);largest=float(extent.max());dimensions[a]={'bbox_native_units':extent.tolist(),'triangles':len(v)}
  flag('units_'+a,largest<q['arch_extent_min_assumed_mm'] or largest>q['arch_extent_max_assumed_mm'],'Plausibilidade grosseira de mm; nenhuma conversão ou escala automática.',largest)
 normalized={a:v@R.T+t for a,v in tri.items()};metrics={'method':'multi5_rmse_original_dev_bank','R':R.tolist(),'t':t.tolist(),'RMSE':float(fit['RMSE']),'template_ID':best['template_ID'],'determinant':det,'orthogonality_error':orth,'rotation_applied_deg':rotation_angle(R),'translation_applied_native_units':float(np.linalg.norm(t)),'scale_applied':1.,'fitness':float(fit['fitness']),'flags':flags,'uncertain':any(f['level']=='attention' for f in flags),'quality_policy':'indicadores heurísticos consultivos; nenhuma porta antiga usada como filtro','clinical_articulation_verified':False,'anatomical_correctness_verified':False,'units':'native_STL_assumed_mm','input_dimensions':dimensions,'templates':[{'ID':f['template_ID'],'RMSE':float(f['fit']['RMSE'])} for f in fits]}
 return normalized,metrics
def normalize_pose(superior,inferior):
 """API curta de integração: retorna R, t, RMSE e flags (demais métricas no dict)."""
 _,result=normalize_pair(superior,inferior);return result
