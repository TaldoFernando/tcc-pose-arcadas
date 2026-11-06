from pathlib import Path
import sys,json,csv,copy,time
import numpy as np
from PIL import Image
OUT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(OUT));sys.path.insert(0,str(OUT/'scripts'))
from render_views import prepare_mesh,render_one,VIEWS
from render_demo import load_mesh
from metrics import compare_images

def cases(camera,appearance):
 for field,delta in [('position',.5),('target',.5),('up',.01)]:
  for axis in range(3):
   for sign in [-1,1]:
    c=copy.deepcopy(camera);a=copy.deepcopy(appearance);c[field][axis]+=sign*delta;yield f'{field}_{"xyz"[axis]}',sign*delta,'native_units' if field!='up' else 'vector_component',c,a
 for field in ['ortho_height','near','far']:
  if field not in camera:continue
  for sign in [-1,1]:
   c=copy.deepcopy(camera);c[field]*=1+sign*.01;yield field,sign,'percent',c,copy.deepcopy(appearance)
 for sign in [-1,1]:
  c=copy.deepcopy(camera);p=np.array(c['position']);t=np.array(c['target']);c['position']=(t+(p-t)*(1+sign*.01)).tolist();yield 'camera_distance',sign,'percent',c,copy.deepcopy(appearance)
 for axis in [0,1]:
  for sign in [-1,1]:
   c=copy.deepcopy(camera);c['resolution'][axis]+=sign;yield 'resolution_'+['width','height'][axis],sign,'pixel',c,copy.deepcopy(appearance)
 for channel in range(3):
  for sign in [-1,1]:
   c=copy.deepcopy(camera);c['background'][channel]=int(np.clip(c['background'][channel]+sign,0,255));yield 'background_'+['R','G','B'][channel],sign,'RGB_unit',c,copy.deepcopy(appearance)
 if camera['projection']=='perspective':
  for sign in [-1,1]:
   c=copy.deepcopy(camera);c['fov_y_deg']+=sign;yield 'fov_y_deg',sign,'degree',c,copy.deepcopy(appearance)
 for field in ['ambient','diffuse']:
  for sign in [-1,1]:
   a=copy.deepcopy(appearance);a[field]+=sign*.01;yield field,sign*.01,'intensity',copy.deepcopy(camera),a

def main():
 cfg=json.loads((OUT/'camera_config_experimental.json').read_text());record=json.loads((OUT/'demo_manifest.json').read_text())[0];mesh=prepare_mesh(load_mesh(record));rows=[]
 for view in VIEWS:
  camera=copy.deepcopy(cfg['views'][view]);camera['resolution']=[256,256];appearance=copy.deepcopy(cfg['appearance']);base,bmask=render_one(mesh,camera,appearance)
  for parameter,delta,unit,c,a in cases(camera,appearance):
   im,mask=render_one(mesh,c,a);resized=im.shape!=base.shape
   if resized:im=np.asarray(Image.fromarray(im).resize((256,256),Image.Resampling.LANCZOS));mask=np.asarray(Image.fromarray(mask).resize((256,256),Image.Resampling.NEAREST))
   metrics=compare_images(im,base,mask,bmask);rows.append({'ID':record['ID'],'view':view,'parameter':parameter,'delta':delta,'delta_unit':unit,'comparison_resized_for_sensitivity_only':resized,**metrics,'fraction_pixels_changed':float(np.mean(np.any(im!=base,axis=2))),'mean_absolute_RGB_change':float(np.mean(abs(im.astype(float)-base.astype(float)))),'training_camera_status':'PLACEHOLDER'})
  print(view,'sensitivity_complete',flush=True)
 with (OUT/'resultados/sensibilidade_experimental.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary=[]
 for p in sorted({r['parameter'] for r in rows}):
  rr=[r for r in rows if r['parameter']==p];summary.append({'parameter':p,'max_one_minus_IoU':max(1-r['IoU'] for r in rr),'max_one_minus_SSIM':max(1-r['SSIM'] for r in rr),'max_centroid_px':max(r['centroid_px'] for r in rr),'max_scale_percent':max(r['scale_percent'] for r in rr),'max_mean_absolute_RGB_change':max(r['mean_absolute_RGB_change'] for r in rr),'training_camera_status':'PLACEHOLDER'})
 with (OUT/'resultados/sensibilidade_resumo.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 (OUT/'resultados/sensibilidade_status.json').write_text(json.dumps({'status':'EXPERIMENTAL_ONLY','ID':record['ID'],'n_perturbations':len(rows),'resolution':[256,256],'not_tested':['perspective FOV: unknown projection; not active in orthographic demonstration','true training material/lighting/texture: unavailable'],'cannot_infer_training_parameter_tolerances':True},indent=2))
if __name__=='__main__':main()
