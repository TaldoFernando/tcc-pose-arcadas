"""Atualiza PNG offline com sombreamento e detalhe dos histogramas."""
from pathlib import Path
import csv,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from executar import preview,read_triangles,plt,OUT
manual=list(csv.DictReader((OUT/'revisao_manual.csv').open()))
for r in manual:preview(read_triangles(OUT/r['arquivo']),r['id'],r['categoria'])
trials=list(csv.DictReader((OUT/'resultados/robustez_ensaios.csv').open()))
for category in ['superior','inferior','indeterminada','registro_mordida']:
 values=np.array([float(r['erro_angular_graus']) for r in trials if r['categoria']==category])
 fig,axs=plt.subplots(1,2,figsize=(11,4))
 axs[0].hist(values,bins=np.linspace(0,180,37),color='#377f9e');axs[0].axvline(5,color='red',linestyle='--',label='Falha >5°');axs[0].legend();axs[0].set_title('Domínio completo: 0–180°')
 upper=max(float(values.max())*1.1,1e-5)
 axs[1].hist(values,bins=np.linspace(0,upper,25),color='#377f9e');axs[1].set_title('Detalhe dos valores observados');axs[1].ticklabel_format(axis='x',style='sci',scilimits=(0,0))
 for ax in axs:ax.set(xlabel='Erro angular geodésico (graus)',ylabel='Ensaios')
 fig.suptitle(f'Robustez — {category} (n={len(values)})');fig.tight_layout();fig.savefig(OUT/'resultados'/f'histograma_{category}.png',dpi=150);plt.close(fig)
print('16 prévias e 4 histogramas atualizados.')
