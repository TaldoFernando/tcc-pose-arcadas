from pathlib import Path
import sys,json,csv,copy
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'etapa6';OUT=BASE/'stl';sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'scripts'))
from sensibilidade import cases
from render_views import read_stl,prepare_mesh,render_one,VIEWS
from metrics import compare_images

def main():
 cfg=json.loads((BASE/'camera_config.json').read_text());fits={r['ID']:r for r in json.loads((OUT/'transformacoes.json').read_text())};pairs={p['id']:p for p in json.loads((ROOT/'etapa5/pares_ids.json').read_text())};labels={r['ID']:int(r['grupo']) for r in csv.DictReader((OUT/'rotulos.csv').open())};selection=json.loads((OUT/'selecao_visual.json').read_text())['IDs'];IDs=[next(i for i in selection if labels[i]==g) for g in [1,2,3]];rows=[]
 for ID in IDs:
  fit=fits[ID];R=np.array(fit['R']);t=np.array(fit['t']);mesh=prepare_mesh({a:read_stl(ROOT/'etapa5'/pairs[ID][a]['arquivo'])@R.T+t for a in ['superior','inferior']})
  for view in VIEWS:
   camera=copy.deepcopy(cfg['views'][view]);camera['resolution']=[256,256];appearance=copy.deepcopy(cfg['appearance']);baseline,bmask=render_one(mesh,camera,appearance)
   for parameter,delta,unit,c,a in cases(camera,appearance):
    image,mask=render_one(mesh,c,a);resize=image.shape!=baseline.shape
    if resize:image=np.asarray(Image.fromarray(image).resize((256,256),Image.Resampling.LANCZOS));mask=np.asarray(Image.fromarray(mask).resize((256,256),Image.Resampling.NEAREST))
    rows.append({'ID':ID,'grupo':labels[ID],'view':view,'parameter':parameter,'delta':delta,'unit':unit,'resized_for_resolution_sensitivity_only':resize,**compare_images(image,baseline,mask,bmask),'mean_absolute_RGB_change':float(np.mean(abs(image.astype(float)-baseline.astype(float))))})
  print(ID,'sensibilidade_concluida',flush=True)
 with (OUT/'sensibilidade_por_ID.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary=[]
 for parameter in sorted({r['parameter'] for r in rows}):
  data=[r for r in rows if r['parameter']==parameter];summary.append({'parameter':parameter,'max_IoU_loss':max(1-r['IoU'] for r in data),'max_SSIM_loss':max(1-r['SSIM'] for r in data),'max_centroid_px':max(r['centroid_px'] for r in data),'max_scale_percent':max(r['scale_percent'] for r in data),'comparison':'perturbed render versus same STL baseline, not training reference'})
 with (OUT/'sensibilidade_resumo.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 (OUT/'sensibilidade_status.json').write_text(json.dumps({'IDs':IDs,'resolution':[256,256],'n_perturbations':len(rows),'FOV':'not applicable, orthographic protocol','not_training_accuracy':True},indent=2))
if __name__=='__main__':main()
