from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]
files=sorted((root/'dados').rglob('*.stl'))
fig,axs=plt.subplots(3,3,figsize=(12,12),subplot_kw={'projection':'3d'})
for ax,idx in zip(axs.flat,np.linspace(0,len(files)-1,9).astype(int)):
 p=files[idx];raw=p.read_bytes(); n=int.from_bytes(raw[80:84],'little');dt=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('a','<u2')]);v=np.frombuffer(raw,dt,offset=84,count=n)['v'].reshape(-1,3)[::100]
 ax.scatter(*v.T,s=.2);ax.set_box_aspect(np.maximum(np.ptp(v,axis=0),1));ax.view_init(25,45);ax.set_title(f'Amostra {idx+1}',fontsize=10)
 ax.set_xlabel('X');ax.set_ylabel('Y');ax.set_zlabel('Z')
(root/'relatorios/amostras_indice.txt').write_text('\n'.join(f'Amostra {i+1}: {files[i].relative_to(root)}' for i in np.linspace(0,len(files)-1,9).astype(int)))
fig.tight_layout();fig.savefig(root/'relatorios/previas.png',dpi=140)
