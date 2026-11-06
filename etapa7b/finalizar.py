"""Apresentação/auditoria adicional, sem alterar treino ou selecionar métodos."""
from pathlib import Path
import csv,json,collections,hashlib,time
import numpy as np
OUT=Path(__file__).resolve().parent
def read(name):return list(csv.DictReader((OUT/name).open()))
def write(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 for name in ['predicoes_oof.csv','residuo_paciente_controle.csv','residuo_paciente_anatomica.csv','residuo_paciente_multi5_rmse.csv']:
  rows=read(name)
  if 'rotulo' not in rows[0]:write(name,[dict(rotulo='modelo substituto',**r) for r in rows])
 p=OUT/'treinamento.json';logs=json.loads(p.read_text())
 for r in logs:r['rotulo']='modelo substituto'
 p.write_text(json.dumps(logs,indent=2,ensure_ascii=False))
 # Estratos: F1 macro não é interpretável dentro de uma única classe verdadeira.
 data=read('metricas_por_paciente.csv');cells=collections.defaultdict(list)
 for r in data:
  if r['condicao'] in ['canonical','realistic'] or (r['condicao']=='rotation' and r['eixo']=='todos'):cells[(r['modelo'],r['condicao'],r['normalizacao'],r['eixo'],r['angulo'],r['grupo'])].append(r)
 group=[]
 for (model,cond,method,axis,angle,g),rr in sorted(cells.items()):
  values=np.array([[float(r[k]) for k in ['acuracia','erro_ordinal_grupo','taxa_troca']] for r in rr]);w=np.random.default_rng(20261106+70000+len(rr)).multinomial(len(rr),[1/len(rr)]*len(rr),size=10000)/len(rr);ci=np.quantile(w@values,[.025,.975],axis=0);row={'rotulo':'modelo substituto','modelo':model,'condicao':cond,'normalizacao':method,'eixo':axis,'angulo':angle,'grupo':g,'conteudos':len(rr)}
  for j,k in enumerate(['acuracia','erro_ordinal_grupo','taxa_troca']):row[k]=values[:,j].mean();row[k+'_IC95_inf']=ci[0,j];row[k+'_IC95_sup']=ci[1,j]
  group.append(row)
 write('metricas_por_grupo_IC95.csv',group)
 # Todas as matrizes estão no CSV; esta figura resume as cinco linhas de base.
 import os;os.environ['MPLCONFIGDIR']='/private/tmp/etapa7b-mpl'
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 pred=read('predicoes_oof.csv');models=['majoritaria','logistica_descritores','substituto_canonico','substituto_aug10','substituto_aug20'];fig,axes=plt.subplots(1,5,figsize=(17,3.5))
 for ax,model in zip(axes,models):
  cm=np.zeros((3,3),int)
  for r in pred:
   if r['model']==model and r['condition']=='canonical':cm[int(r['grupo_real'])-1,int(r['predicao'])-1]+=1
  ax.imshow(cm,cmap='Blues',vmin=0,vmax=27)
  for i in range(3):
   for j in range(3):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>13 else 'black')
  ax.set_xticks(range(3));ax.set_xticklabels([1,2,3]);ax.set_yticks(range(3));ax.set_yticklabels([1,2,3]);ax.set_xlabel('Grupo predito');ax.set_title(model.replace('substituto_',''));ax.set_ylabel('Grupo real')
 fig.suptitle('MODELO SUBSTITUTO — confusão canônica out-of-fold (63 conteúdos)');fig.tight_layout();fig.savefig(OUT/'confusao_canonica.png',dpi=160);plt.close(fig)
 from PIL import Image
 borders=[]
 for folder in (OUT/'previews').iterdir():
  for path in folder.glob('*.png'):
   im=np.array(Image.open(path));edge=np.concatenate([im[0],im[-1],im[:,0],im[:,-1]]);borders.append({'ID':folder.name,'vista':path.stem,'foreground_on_border':bool((np.max(abs(edge.astype(float)-32),axis=1)>5).any())})
 write('enquadramento_canonico.csv',borders)
 time_rows=[json.load(open(p)) for p in (OUT/'features').glob('P*.json')];write('tempo_por_ID.csv',[dict(rotulo='modelo substituto',**r) for r in sorted(time_rows,key=lambda r:r['ID'])])
 readme=OUT/'README.md';text=readme.read_text();text+='\n## Auditoria final e apresentação adicional\n\nAntes de qualquer treino supervisionado, o congelamento inicial foi atualizado para parear as ablations: mesma inicialização, máscaras de dropout, ordem de minibatches e número de atualizações por fold. Somente o sorteio das poses aumentadas difere. O motivo e a data constam em `congelamento.json`; o manifesto inicial foi preservado em `historico/`. Nenhuma predição de teste havia sido produzida nessa atualização.\n\n'
 text+='O rasterizador e o preparador também estão cobertos pelo manifesto final. A extração repetida de P001, com o mesmo tamanho de batch, reproduziu os embeddings exatamente; mudar o tamanho do batch altera últimos bits de convoluções CPU (diferença máxima observada 6,51e-5), sem alterar os pixels. Ver `verificacao_piloto.json`.\n\n'
 text+='`metricas_por_grupo_IC95.csv` apresenta acurácia, erro ordinal e troca por grupo com bootstrap de conteúdos dentro do grupo. F1 macro não é apresentado dentro de uma única classe verdadeira. `confusao_canonica.png` resume as matrizes canônicas; todas as condições estão no CSV de confusões. `enquadramento_canonico.csv` audita contato do objeto com a borda; isso é um indício de enquadramento, não certificado de anatomia.\n\n'
 med=lambda k:float(np.median([r[k] for r in time_rows]));text+=f"Cada conteúdo teve 213 condições (incluindo 12 poses reservadas ao treino aumentado), 1.278 imagens; total de 13.419 condições e 80.514 imagens. Medianas por conteúdo: renderização {med('render_seconds'):.1f} s; registro {med('fit_seconds'):.1f} s; execução total {med('total_seconds'):.1f} s. Tempos medidos sob concorrência de processos CPU; não são latência de produção.\n\n"
 text+='Os 63 conteúdos e cinco classificadores/baselines produzem 63.315 predições de teste OOF, preservadas com IDs. Rotações puras com as mesmas amostras são essencialmente um teste de equivariância: o resíduo numérico próximo de zero não demonstra robustez realista. Os ensaios realistas usam novas amostras e alterações independentes.\n\n'
 text+='Há risco de aprender características do escaneamento/base e da composição deste pequeno conjunto, além da morfologia relevante. A interpretação permanece limitada ao modelo substituto e aos dados descritos.\n'
 readme.write_text(text)
 # Manifesto de saídas: permite verificar resultados sem nomes de pacientes.
 files=[p for p in OUT.iterdir() if p.is_file() and p.suffix in ['.csv','.json','.png','.md','.py'] and p.name!='manifesto_resultados.json'];manifest={'rotulo':'modelo substituto','generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}};(OUT/'manifesto_resultados.json').write_text(json.dumps(manifest,indent=2));print('Apresentação final e rótulos MODELO SUBSTITUTO registrados.')
if __name__=='__main__':main()
