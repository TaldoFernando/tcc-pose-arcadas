from pathlib import Path
import sys,json,csv,time,hashlib
import numpy as np
from PIL import Image,ImageDraw
OUT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(OUT))
from render_views import read_stl,prepare_mesh,render_views,render_one,VIEWS

def load_mesh(record):
 R=np.asarray(record['R']);t=np.asarray(record['t']);return {a:read_stl(OUT/p)@R.T+t for a,p in record['meshes'].items()}

def main():
 cfg=json.loads((OUT/'camera_config_experimental.json').read_text());manifest=json.loads((OUT/'demo_manifest.json').read_text());performance=[];hashes=[];start=time.perf_counter();dummy={'superior':np.array([[[0,0,0],[1,0,0],[0,1,0]]],float),'inferior':np.array([[[0,0,-1],[1,0,-1],[0,1,-1]]],float)};render_views(dummy,cfg);jit=time.perf_counter()-start
 cellw=118;cellh=118;rowh=145;left=70;header=65;sheet=Image.new('RGB',(left+18*cellw,header+len(manifest)*rowh),(248,248,248));draw=ImageDraw.Draw(sheet);draw.text((10,8),'DEMONSTRACAO PLACEHOLDER — NAO CALIBRADA COM TREINO. Colunas: render / treino indisponivel / diferenca indisponivel.',fill='black')
 for j,name in enumerate(VIEWS):
  draw.text((left+j*3*cellw+5,28),name,fill='black')
  for k,label in enumerate(['RENDER PLACEHOLDER','TREINO AUSENTE','DIFERENCA AUSENTE']):draw.text((left+(j*3+k)*cellw+3,46),label,fill='black')
 for n,r in enumerate(manifest):
  start=time.perf_counter();mesh=prepare_mesh(load_mesh(r));prepare=time.perf_counter()-start;start=time.perf_counter();images=render_views(mesh,cfg);elapsed=time.perf_counter()-start;performance.append({'ID':r['ID'],'prepare_seconds':prepare,'six_views_seconds':elapsed,'total_seconds':prepare+elapsed,'resolution':'512x512','supersampling':2,'training_equivalence':False});target=OUT/'demonstracao'/r['ID'];target.mkdir(parents=True,exist_ok=True);draw.text((3,header+n*rowh+10),r['ID'],fill='black')
  for j,(name,im) in enumerate(images.items()):
   Image.fromarray(im).save(target/f'{name}.png');p=Image.fromarray(im);p.thumbnail((cellw-4,cellh-4));x=left+j*3*cellw;y=header+n*rowh;sheet.paste(p,(x,y))
   for k in [1,2]:
    xk=x+k*cellw;draw.rectangle((xk,y,xk+cellw-4,y+cellh-4),fill=(218,218,218));draw.text((xk+8,y+40),'NAO DISPONIVEL',fill=(50,50,50))
   if n<2:
    repeated=render_one(mesh,cfg['views'][name],cfg['appearance'])[0];hashes.append({'ID':r['ID'],'view':name,'identical_repeat':bool(np.array_equal(im,repeated)),'sha256_pixels':hashlib.sha256(im.tobytes()).hexdigest()})
  print(r['ID'],'render_6_seconds',round(elapsed,4),flush=True)
 sheet.save(OUT/'resultados/folha_10_IDs_PLACEHOLDER.png')
 for filename,rows in [('tempo_por_ID.csv',performance),('determinismo.csv',hashes)]:
  with (OUT/'resultados'/filename).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (OUT/'resultados/performance_resumo.json').write_text(json.dumps({'n_IDs':len(performance),'jit_startup_seconds':jit,'six_views_seconds_median':float(np.median([r['six_views_seconds'] for r in performance])),'six_views_seconds_max':max(r['six_views_seconds'] for r in performance),'all_12_repeat_images_identical':all(r['identical_repeat'] for r in hashes),'renderer':'CPU numba, offscreen, single-thread deterministic; no GPU/network','training_equivalence':False},indent=2))
if __name__=='__main__':main()
