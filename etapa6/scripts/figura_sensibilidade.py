from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parents[1];rows=list(csv.DictReader((OUT/'resultados/sensibilidade_resumo.csv').open()));rows=sorted(rows,key=lambda r:float(r['max_one_minus_IoU']),reverse=True)
fig,axs=plt.subplots(1,2,figsize=(12,8));names=[r['parameter'] for r in rows]
for ax,key,title in zip(axs,['max_one_minus_IoU','max_one_minus_SSIM'],['Maior perda de IoU','Maior perda de SSIM']):
 ax.barh(names,[float(r[key]) for r in rows]);ax.invert_yaxis();ax.set_xlabel(title);ax.grid(axis='x',alpha=.2)
fig.suptitle('Sensibilidade EXPERIMENTAL — câmeras PLACEHOLDER, não tolerância de treino\nPerturbações têm unidades diferentes; conferir CSV. Pior resultado entre seis vistas.');fig.tight_layout();fig.savefig(OUT/'resultados/sensibilidade_experimental.png',dpi=160)
