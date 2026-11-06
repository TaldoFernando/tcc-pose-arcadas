from pathlib import Path
import sys,json,tempfile,hashlib
import numpy as np
from PIL import Image
OUT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(OUT))
from render_views import prepare_mesh,render_one
from calibrate_cameras import optimize_view,load_records
from contact_sheet import make_contact_sheet

def main():
 frozen=hashlib.sha256((OUT/'camera_config.json').read_bytes()).hexdigest();v=np.array([[-1,-1,-.5],[1,-.7,-.5],[.3,1,-.5],[.1,.1,1]],float);tri=v[np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])];mesh=prepare_mesh({'superior':tri,'inferior':tri+np.array([0,0,-1.5])});camera={'projection':'orthographic','position':[0,-10,3],'target':[0,0,0],'up':[0,0,1],'resolution':[48,48],'ortho_height':5,'near':.1,'far':100,'mesh':'ambas','background':[16,16,16]};appearance={'background':[16,16,16],'material_rgb':[220,220,220],'ambient':.35,'diffuse':.65,'light_direction_camera':[-.3,.5,-1.],'shading':'smooth','two_sided':True,'supersampling':1}
 image,_=render_one(mesh,camera,appearance)
 with tempfile.TemporaryDirectory(prefix='etapa6-synthetic-') as temporary:
  path=Path(temporary)/'reference.png';Image.fromarray(image).save(path);record={'images':{'Frontal':str(path)},'_mesh':mesh};best,candidates=optimize_view([record],'Frontal',camera,appearance,seed=7,budget=0)
  checks={'synthetic_fixture_only':True,'not_patient_calibration':True,'both_projection_branches_executed':{r['projection'] for r in candidates}=={'orthographic','perspective'},'finite_native_objective':bool(np.isfinite(best['native_calibration_loss']))}
  manifest=Path(temporary)/'unconfirmed.json';manifest.write_text(json.dumps({'records':[{'ID':'P001','confirmed_pair':False,'confirmed_training_source':False}]}))
  try:load_records(manifest);checks['unconfirmed_source_rejected']=False
  except ValueError:checks['unconfirmed_source_rejected']=True
  try:make_contact_sheet([],{},Path(temporary)/'fake.png');checks['missing_contact_references_rejected']=False
  except ValueError:checks['missing_contact_references_rejected']=True
 checks['training_config_unchanged']=frozen==hashlib.sha256((OUT/'camera_config.json').read_bytes()).hexdigest();(OUT/'resultados/testes_calibrador.json').write_text(json.dumps(checks,indent=2));assert all(checks.values());print('CALIBRATOR SYNTHETIC IMPLEMENTATION CHECKS PASS; no patient calibration executed')
if __name__=='__main__':main()
