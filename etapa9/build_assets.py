"""Prepara configuração e referências próprias locais; não recebe uploads."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa9'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 camera=json.load(open(ROOT/'etapa7b/camera_config_proprio.json'));(OUT/'camera_config.json').write_text(json.dumps(camera,indent=2,ensure_ascii=False))
 units=json.load(open(ROOT/'etapa7b/unidades.json'));split=json.load(open(ROOT/'etapa5/divisao_original.json'));ids=[u['ID'] for u in units if all(i in split['desenvolvimento'] for i in u['aliases'])];refs={}
 for view in camera['views']:
  images=[np.asarray(Image.open(ROOT/'etapa7b/previews'/i/f'{view}.png'),float) for i in ids];mean=np.rint(np.mean(images,axis=0)).astype('uint8');p=OUT/'static/reference'/f'{view}.png';Image.fromarray(mean).save(p);refs[view]='/static/reference/'+view+'.png'
 seeds={
 'Angulada':[('linha média inf',.55,.65,'A'),('molar esq',.21,.53,'A'),('molar dir',.76,.52,'A'),('fissura',.42,.58,'B')],
 'Direita':[('incisal sup',.22,.48,'G'),('canino sup',.36,.48,'A'),('molar MV',.57,.50,'A'),('molar inf',.76,.61,'A')],
 'Esquerda':[('pré-maxila',.24,.36,'G'),('incisal sup',.26,.46,'G'),('incisal inf',.31,.48,'G'),('molar MV',.54,.48,'A'),('molar inf',.62,.53,'A')],
 'Up':[('fissura',.53,.38,'B'),('borda seg menor',.46,.40,'B'),('borda seg maior',.61,.39,'B'),('papila incisiva',.50,.45,'O'),('molar esq',.22,.72,'A'),('molar dir',.84,.70,'A'),('tuberosidade esq',.20,.84,'A'),('tuberosidade dir',.78,.84,'A'),('rafe posterior',.52,.85,'A')],
 'Frontal':[('linha média inf',.49,.60,'A'),('incisal inf',.49,.55,'G'),('fissura',.42,.51,'B'),('incisal sup',.58,.48,'G'),('plano oclusal esq',.24,.56,'A'),('plano oclusal dir',.80,.55,'A')],
 'Inferior':[('linha média inf',.48,.84,'A'),('canino esq',.32,.74,'A'),('canino dir',.63,.76,'A'),('molar esq',.23,.38,'A'),('molar dir',.76,.37,'A'),('trígono retromolar esq',.23,.25,'A'),('trígono retromolar dir',.74,.26,'A')]}
 landmarks=[]
 for view,points in seeds.items():
  for label,x,y,category in points:landmarks.append({'number':len(landmarks)+1,'label':label,'view':view,'uv':[x,y],'category':category})
 cfg={'version':'etapa9.v1','normalization':'multi5_rmse_original_dev_bank','normalization_model':'../etapa6/stl/modelo_normalizacao.npz','camera_config':'camera_config.json','original_training_cameras':'PLACEHOLDER','original_training_reference':'PLACEHOLDER','model':{'mode':'stub','class_semantics':'PLACEHOLDER','Goslon_AI_loaded':False,'substitute_7B_loaded':False},'reference':{'kind':'MEDIA_CANONICA_PROPRIA_DESENVOLVIMENTO_NAO_TREINO_ORIGINAL','IDs':ids,'n_contents':len(ids),'views':refs},'quality':{'advisory_only':True,'calibrated_against_landmarks':False,'rmse_warn_mm':4.,'candidate_disagreement_warn_deg':10.,'template_relative_gap_warn':.02,'fitness_warn':.8,'arch_extent_min_assumed_mm':15.,'arch_extent_max_assumed_mm':150.},'limits':{'request_bytes':64*1024*1024,'file_bytes':30*1024*1024,'triangles_per_arch':600000,'concurrent_jobs':1,'robustness_N_max':5},'landmarks_mock':landmarks,'privacy':{'STL_saved':False,'uploads_external':False,'storage':'RAM local; sem banco ou cache de requisições'}}
 (OUT/'config.json').write_text(json.dumps(cfg,indent=2,ensure_ascii=False))
 sources=[ROOT/'etapa5/anatomical_pair.py',ROOT/'etapa5/rigid_icp.py',ROOT/'etapa6/render_views.py',ROOT/'etapa6/stl/modelo_normalizacao.npz',ROOT/'etapa7b/camera_config_proprio.json']
 freeze={'normalization_not_retrained':True,'normalization_not_updated_from_test_landmarks':True,'bank_IDs':['P016','P004','P045','P029','P002'],'source_files':{str(p.relative_to(ROOT)):sha(p) for p in sources},'camera_copy_sha256':sha(OUT/'camera_config.json'),'config_sha256':sha(OUT/'config.json')};(OUT/'congelamento.json').write_text(json.dumps(freeze,indent=2));print('Configuração, banco congelado e referências próprias:',len(ids),'conteúdos; landmarks mock:',len(landmarks))
if __name__=='__main__':main()
