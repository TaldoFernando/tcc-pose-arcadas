from pathlib import Path
import sys,json,csv,copy
import numpy as np
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'etapa6';OUT=BASE/'stl';sys.path.insert(0,str(BASE))
from render_views import read_stl,prepare_mesh,render_one

def main():
 rows=list(csv.DictReader((OUT/'sensibilidade_resumo.csv').open()));rows.sort(key=lambda r:float(r['max_IoU_loss']),reverse=True);fig,axs=plt.subplots(1,2,figsize=(11,8))
 for ax,key,title in zip(axs,['max_IoU_loss','max_SSIM_loss'],['Maior perda de IoU','Maior perda de SSIM']):
  ax.barh([r['parameter'] for r in rows],[float(r[key]) for r in rows]);ax.invert_yaxis();ax.set_xlabel(title);ax.grid(axis='x',alpha=.2)
 fig.suptitle('Protocolo STL — resposta às perturbações; não é acurácia de treino\nUnidades de perturbação diferem por parâmetro; três IDs, seis vistas.');fig.tight_layout();fig.savefig(OUT/'sensibilidade.png',dpi=160);plt.close(fig)
 ID='P003';fit=next(r for r in json.loads((OUT/'transformacoes.json').read_text()) if r['ID']==ID);pair=next(r for r in json.loads((ROOT/'etapa5/pares_ids.json').read_text()) if r['id']==ID);R=np.array(fit['R']);t=np.array(fit['t']);mesh=prepare_mesh({a:read_stl(ROOT/'etapa5'/pair[a]['arquivo'])@R.T+t for a in ['superior','inferior']});cfg=json.loads((BASE/'camera_config.json').read_text());camera=cfg['views']['Frontal'];baseline,_=render_one(mesh,camera,cfg['appearance']);sheet=Image.new('RGB',(990,1040),'white');d=ImageDraw.Draw(sheet)
 cases=[];c=copy.deepcopy(camera);c['target'][0]+=.5;cases.append(('alvo X +0,5 unidade',c));c=copy.deepcopy(camera);c['ortho_height']*=1.01;cases.append(('extensao +1%',c));c=copy.deepcopy(camera);p=np.array(c['position']);q=np.array(c['target']);c['position']=(q+(p-q)*1.01).tolist();cases.append(('distancia +1% (ortografica)',c))
 for n,(label,c) in enumerate(cases):
  im,_=render_one(mesh,c,cfg['appearance']);diff=np.clip(abs(im.astype(float)-baseline.astype(float))*4,0,255).astype(np.uint8);y=20+n*340;d.text((10,y),ID+' Frontal — '+label,fill='black')
  for j,(a,name) in enumerate([(baseline,'base'),(im,'perturbada'),(diff,'diferenca absoluta x4')]):
   thumbnail=Image.fromarray(a);thumbnail.thumbnail((320,300));sheet.paste(thumbnail,(j*330,y+25));d.text((j*330+5,y+320),name,fill='black')
 sheet.save(OUT/'sensibilidade_exemplos.png')
if __name__=='__main__':main()
