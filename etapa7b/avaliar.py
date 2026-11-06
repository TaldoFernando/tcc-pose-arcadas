"""CV agrupada e relatórios do MODELO SUBSTITUTO, sem ajustar folds de teste."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
os.environ['MPLCONFIGDIR']='/private/tmp/etapa7b-mpl'
from pathlib import Path
import json,csv,hashlib,time,collections
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa7b';SEED=20261106
def load(p):return json.loads(Path(p).read_text())
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False))
def csvsave(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def freeze_check():
 freeze=load(OUT/'congelamento.json')
 for name,h in freeze['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
def training():
 import torch
 from torch import nn
 from sklearn.linear_model import LogisticRegression
 from sklearn.preprocessing import StandardScaler
 from sklearn.pipeline import make_pipeline
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True);units=load(OUT/'unidades.json');data={}
 for u in units:
  z=np.load(OUT/'features'/f"{u['ID']}.npz");records=json.loads(str(z['records']));data[u['ID']]={'features':z['features'].reshape(len(records),-1),'descriptors':z['descriptors'],'records':records}
 rows=[];traininglog=[];(OUT/'checkpoints').mkdir(exist_ok=True)
 class Head(nn.Sequential):
  def __init__(self):super().__init__(nn.LayerNorm(3456),nn.Linear(3456,64),nn.GELU(),nn.Dropout(.2),nn.Linear(64,3))
 for fold in range(5):
  train=[u for u in units if u['fold']!=fold];test=[u for u in units if u['fold']==fold];y=np.array([u['grupo']-1 for u in train]);freq=np.bincount(y,minlength=3);major=int(np.argmax(freq))
  logistic=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,class_weight='balanced',random_state=SEED+fold));logistic.fit(np.stack([data[u['ID']]['descriptors'][0] for u in train]),y)
  models={}
  for variant,limit in enumerate([0,10,20]):
   name=['substituto_canonico','substituto_aug10','substituto_aug20'][variant];seed=SEED+100*fold;torch.manual_seed(seed);rng=np.random.default_rng(seed+10000*variant);order_rng=np.random.default_rng(seed);net=Head();optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.01);lossfn=nn.CrossEntropyLoss(weight=torch.tensor(len(y)/(3*freq),dtype=torch.float32));losses=[]
   for epoch in range(80):
    xs=[]
    for u in train:
     d=data[u['ID']];idx=0
     if limit and rng.random()<.5:
      choices=[i for i,r in enumerate(d['records']) if r['condition']=='augmentation' and r['augmentation']==limit];idx=int(rng.choice(choices))
     xs.append(d['features'][idx])
    x=torch.tensor(np.stack(xs));target=torch.tensor(y,dtype=torch.long);order=order_rng.permutation(len(train));net.train();epochloss=0.
    for start in range(0,len(train),8):
     ix=order[start:start+8];optimizer.zero_grad();loss=lossfn(net(x[ix]),target[ix]);loss.backward();optimizer.step();epochloss+=float(loss.detach())*len(ix)
    losses.append(epochloss/len(train))
   net.eval();models[name]=net
   torch.save({'model_label':'MODELO SUBSTITUTO','state_dict':net.state_dict(),'fold':fold,'seed':seed,'train_IDs':[u['ID'] for u in train],'test_IDs':[u['ID'] for u in test],'augmentation_max_deg':limit,'architecture':'LayerNorm(3456)-Linear64-GELU-Dropout0.2-Linear3'},OUT/'checkpoints'/f'{name}_fold{fold}.pt')
   traininglog.append({'model':name,'fold':fold,'seed':seed,'train_contents':len(train),'test_contents':len(test),'epochs':80,'first_loss':losses[0],'last_loss':losses[-1],'train_group_counts':freq.tolist(),'test_used_for_selection':False})
  for u in test:
   d=data[u['ID']];indices=[i for i,r in enumerate(d['records']) if r['condition']!='augmentation'];x=d['features'][indices];ds=d['descriptors'][indices]
   predictions={'majoritaria':np.full(len(indices),major),'logistica_descritores':logistic.predict(ds)}
   with torch.inference_mode():
    for name,net in models.items():predictions[name]=net(torch.tensor(x)).argmax(1).numpy()
   for name,pred in predictions.items():
    canonical=int(pred[0])+1
    for j,i in enumerate(indices):
     r=d['records'][i];p=int(pred[j])+1;rows.append(dict(r,model=name,fold=fold,grupo_real=u['grupo'],predicao=p,predicao_canonica=canonical,acerto=int(p==u['grupo']),erro_ordinal=abs(p-u['grupo']),troca=int(p!=canonical),template_bank_content=int(u['ID'] in ['P016','P004','P045','P029','P002'])))
  print('TREINO MODELO SUBSTITUTO: fold',fold,'concluído; sem seleção por teste',flush=True)
 csvsave('predicoes_oof.csv',rows);save('treinamento.json',traininglog)
 # Artefatos dos baselines são reproduzíveis pelo script e folds, sem pickle externo.
 return rows,units
def metrics(rows,units):
 lookup={u['ID']:u for u in units};models=sorted({r['model'] for r in rows});cells=collections.defaultdict(list)
 for r in rows:
  key=(r['model'],r['condition'],r['method'],r['axis'],r['angle']);cells[key].append(r)
  if r['condition']=='rotation':cells[(r['model'],r['condition'],r['method'],'todos',r['angle'])].append(r)
 # Um bloco de bootstrap por conjunto de IDs, reutilizado em todas as condições.
 boot={};summaries=[];patientrows=[];confusions=[]
 def calculate(rs,ids):
  stats=np.zeros((len(ids),11));index={i:k for k,i in enumerate(ids)}
  for r in rs:
   k=index[r['ID']];stats[k,(int(r['grupo_real'])-1)*3+int(r['predicao'])-1]+=1;stats[k,9]+=float(r['erro_ordinal']);stats[k,10]+=float(r['troca'])
  counts=stats[:,:9].sum(1);assert (counts>0).all();stats/=counts[:,None]
  key=tuple(ids)
  if key not in boot:boot[key]=np.random.default_rng(SEED+90000+len(ids)).multinomial(len(ids),[1/len(ids)]*len(ids),size=10000).astype(np.float64)/len(ids)
  draws=boot[key]@stats;point=stats.mean(0)
  def unpack(s):
   cm=s[...,:9].reshape(s.shape[:-1]+(3,3));tp=np.diagonal(cm,axis1=-2,axis2=-1);den=cm.sum(-1)+cm.sum(-2);f1=np.divide(2*tp,den,out=np.zeros_like(tp),where=den>0).mean(-1)
   return np.stack([tp.sum(-1),f1,s[...,9],s[...,10]],axis=-1)
  est=unpack(point);ci=np.quantile(unpack(draws),[.025,.975],axis=0);return est,ci,stats,counts
 for key,rs in sorted(cells.items()):
  model,cond,method,axis,deg=key;ids=sorted({r['ID'] for r in rs});est,ci,stats,counts=calculate(rs,ids)
  base={'rotulo':'modelo substituto','modelo':model,'condicao':cond,'normalizacao':method,'eixo':axis,'angulo':deg,'conteudos':len(ids),'ensaios':len(rs)}
  row=base.copy()
  for j,name in enumerate(['acuracia','f1_macro','erro_ordinal_grupo','taxa_troca']):row[name]=float(est[j]);row[name+'_IC95_inf']=float(ci[0,j]);row[name+'_IC95_sup']=float(ci[1,j])
  summaries.append(row)
  cm=stats[:,:9].sum(0).reshape(3,3)
  for y in range(3):
   for pred in range(3):confusions.append(dict(base,grupo_real=y+1,predicao=pred+1,conteudos_equivalentes=float(cm[y,pred])))
  for i,identifier in enumerate(ids):
   patientrows.append(dict(base,ID=identifier,grupo=lookup[identifier]['grupo'],ensaios_paciente=int(counts[i]),acuracia=float(np.trace(stats[i,:9].reshape(3,3))),erro_ordinal_grupo=float(stats[i,9]),taxa_troca=float(stats[i,10])))
 csvsave('metricas_IC95.csv',summaries);csvsave('metricas_por_paciente.csv',patientrows);csvsave('matrizes_confusao.csv',confusions)
 thresholds=[]
 for model in models:
  for method in ['nenhuma','controle','anatomica','multi5_rmse']:
   for ax in ['todos','vertical','anteroposterior','lateral']:
    rr=sorted([r for r in summaries if r['modelo']==model and r['condicao']=='rotation' and r['normalizacao']==method and r['eixo']==ax],key=lambda r:r['angulo'])
    thresholds.append({'rotulo':'modelo substituto','modelo':model,'normalizacao':method,'eixo':ax,'primeiro_angulo_troca_maior_5':next((r['angulo'] for r in rr if r['taxa_troca']>.05),'não excedeu até 20°'),'primeiro_angulo_troca_maior_10':next((r['angulo'] for r in rr if r['taxa_troca']>.10),'não excedeu até 20°')})
 csvsave('limiares_tolerancia.csv',thresholds)
 # Resíduos geométricos não dependem do classificador; cada ensaio entra uma vez.
 pose=[]
 for method in ['controle','anatomica','multi5_rmse']:
  rs=[r for r in rows if r['model']=='substituto_canonico' and r['condition']=='realistic' and r['method']==method];errors=np.array([float(r['pose_error_deg']) for r in rs]);per=[]
  for i in sorted({r['ID'] for r in rs}):
   e=np.array([float(r['pose_error_deg']) for r in rs if r['ID']==i]);per.append({'ID':i,'method':method,'mediana_erro_deg':float(np.median(e)),'media_erro_deg':float(e.mean()),'falha_2':float((e>2).mean()),'falha_3':float((e>3).mean()),'falha_5':float((e>5).mean()),'falha_10':float((e>10).mean())})
  pose.append({'rotulo':'modelo substituto; resíduo geométrico','metodo':method,'mediana_graus':float(np.median(errors)),'Q25':float(np.quantile(errors,.25)),'Q75':float(np.quantile(errors,.75)),'maximo':float(errors.max()),'taxa_maior_5':float((errors>5).mean())})
  csvsave(f'residuo_paciente_{method}.csv',per)
 save('residuos_pose.json',pose)
 # Diferenças pareadas: mesma pessoa, mesma perturbação, mesmo fold.
 paired=[]
 for cond in ['canonical','realistic']:
  for method in (['nenhuma'] if cond=='canonical' else ['nenhuma','controle','anatomica','multi5_rmse']):
   for name in ['substituto_aug10','substituto_aug20']:
    a={r['ID']:r for r in patientrows if r['modelo']=='substituto_canonico' and r['condicao']==cond and r['normalizacao']==method};b={r['ID']:r for r in patientrows if r['modelo']==name and r['condicao']==cond and r['normalizacao']==method};ids=sorted(a);w=boot[tuple(ids)]
    for metric in ['acuracia','erro_ordinal_grupo','taxa_troca']:
     d=np.array([b[i][metric]-a[i][metric] for i in ids]);ci=np.quantile(w@d,[.025,.975]);paired.append({'rotulo':'modelo substituto','modelo_comparado':name,'referencia':'substituto_canonico','condicao':cond,'normalizacao':method,'metrica':metric,'diferenca':float(d.mean()),'IC95_inf':float(ci[0]),'IC95_sup':float(ci[1])})
 csvsave('diferencas_pareadas_IC95.csv',paired)
 # Sensibilidade à inclusão dos cinco conteúdos-template do banco congelado.
 subset=[]
 for model in models:
  rr=[r for r in rows if r['model']==model and r['condition']=='canonical' and not r['template_bank_content']];ids=sorted({r['ID'] for r in rr});est,ci,_,_=calculate(rr,ids);subset.append({'rotulo':'modelo substituto','modelo':model,'conteudos_sem_templates':len(ids),'acuracia':float(est[0]),'IC95_inf':float(ci[0,0]),'IC95_sup':float(ci[1,0]),'F1_macro':float(est[1]),'erro_ordinal_grupo':float(est[2])})
 csvsave('sensibilidade_sem_templates.csv',subset)
 return summaries,thresholds,pose
def figures(summaries,pose):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,3,figsize=(15,4),sharey=True)
 for ax,axis in zip(axes,['vertical','anteroposterior','lateral']):
  for model in ['substituto_canonico','substituto_aug10','substituto_aug20']:
   rs=sorted([r for r in summaries if r['modelo']==model and r['condicao']=='rotation' and r['normalizacao']=='nenhuma' and r['eixo']==axis],key=lambda r:r['angulo']);xx=[0]+[r['angulo'] for r in rs];yy=[0]+[100*r['taxa_troca'] for r in rs];ax.plot(xx,yy,'o-',label=model.replace('substituto_',''))
  ax.axhline(5,color='gray',ls=':');ax.axhline(10,color='gray',ls='--');ax.set_title(axis);ax.set_xlabel('Rotação conhecida (graus)');ax.grid(alpha=.2)
 axes[0].set_ylabel('Troca de predição (%)');axes[-1].legend();fig.suptitle('Modelo substituto — tolerância à pose sem normalização');fig.tight_layout();fig.savefig(OUT/'tolerancia_pose.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(12,4))
 for ax,metric in zip(axes,['acuracia','taxa_troca']):
  for method in ['nenhuma','controle','anatomica','multi5_rmse']:
   rr=sorted([r for r in summaries if r['modelo']=='substituto_canonico' and r['condicao']=='rotation' and r['normalizacao']==method and r['eixo']=='todos'],key=lambda r:r['angulo']);ax.plot([r['angulo'] for r in rr],[100*r[metric] for r in rr],'o-',label=method)
  ax.set_ylabel(metric+' (%)');ax.set_xlabel('Rotação conhecida (graus)');ax.grid(alpha=.2);ax.legend()
 fig.suptitle('Modelo substituto canônico — efeito da normalização');fig.tight_layout();fig.savefig(OUT/'normalizacao_pose.png',dpi=160);plt.close(fig)
 # Folha apenas IDs; não expõe os nomes originais.
 from PIL import Image,ImageDraw
 selected=[u['ID'] for u in load(OUT/'unidades.json')][::6][:10];sheet=Image.new('RGB',(6*224+110,len(selected)*150+45),'white');draw=ImageDraw.Draw(sheet);draw.text((8,8),'MODELO SUBSTITUTO — seis vistas próprias, apenas IDs',fill='black')
 for j,i in enumerate(selected):
  draw.text((8,50+j*150),i,fill='black')
  for k,v in enumerate(['Angulada','Direita','Esquerda','Up','Frontal','Inferior']):sheet.paste(Image.open(OUT/'previews'/i/f'{v}.png').resize((145,145)),(110+k*224,45+j*150));draw.text((110+k*224,30),v,fill='black')
 sheet.save(OUT/'folha_10_IDs.png')
def readme(summaries,thresholds,pose):
 canonical=[r for r in summaries if r['condicao']=='canonical'];real=[r for r in summaries if r['condicao']=='realistic'];lines=['# Etapa 7B — MODELO SUBSTITUTO','', 'Este experimento treina um modelo substituto de três grupos a partir de STL locais. Não é o Goslon AI e não mede o desempenho desse sistema. As câmeras originais continuam PLACEHOLDER. Não há afirmação de correção anatômica.','', '## Dados e protocolo congelado','', '69 IDs correspondem a 64 conteúdos geométricos únicos. P021/P039 têm grupos conflitantes e foram excluídos do treino e da avaliação principal. Restam 63 conteúdos: grupo 1 = 27, grupo 2 = 13, grupo 3 = 23. Um representante por conteúdo; aliases permanecem no mesmo fold. A tabela privada ID→pasta anterior permanece em `../etapa5/privado/id_pasta_local.csv`; nenhum nome de pasta é publicado aqui.','', 'GOSLON: 1 = 7, 2 = 21, 3 = 13, 4 = 17, 5 = 4 conteúdos não conflitantes. Há também conflito GOSLON P066/P067. Cinco classes não foram treinadas: a classe 5 possui menos de cinco conteúdos únicos. Grupos 1–3 não foram convertidos em rótulos GOSLON 1–5. O erro ordinal é distância entre grupos, com a suposição de que 1<2<3. Rótulos vêm dos nomes, não de revisão clínica.','', 'Antes de extrair features e treinar, foram fixados `protocolo.json`, `camera_config_proprio.json`, `conteudos_folds.csv` e hashes de código/pesos/banco em `congelamento.json`. Cinco folds estratificados por grupo, agrupados por hash do par, seed 20261106. Nenhum hiperparâmetro, época, câmera ou normalizador foi escolhido pelo desempenho de teste.','', 'MobileNet V3 Small pré-treinada em ImageNet1K (torchvision IMAGENET1K_V1), backbone congelado e em eval; pooling de 576 dimensões por vista, concatenação de seis vistas. Cabeça: LayerNorm(3456), Linear64, GELU, Dropout0,2, Linear3. AdamW, lr 0,001, weight decay 0,01, 80 épocas, batch 8; última época. Pesos de classe calculados só no treino. Baselines: maioria do treino e regressão logística C=1 com StandardScaler ajustado só no treino, sobre 48 descritores de silhueta/intensidade.','', 'Os pesos genéricos foram baixados do endereço público oficial PyTorch registrado no congelamento; nenhum STL, imagem, rótulo ou identificação foi enviado. Todas as predições, renderizações e ajustes ocorreram localmente.','', 'Treino principal: somente pose canônica multi5_rmse. Ablations: mesma cabeça e número de atualizações; a cada conteúdo/época, 50% canônico ou uma de seis rotações 3D pré-geradas, eixos sorteados e ângulo uniforme ±10° ou ±20°. Seeds constam no protocolo e em treinamento.json. Não são rotações 2D das imagens.','', '## Câmeras próprias','', 'Seis vistas ortográficas 224×224, altura ortográfica fixa 110 unidades nativas presumidas mm, distância 200, alvo na origem canônica e sem autozoom por paciente. Material cinza, fundo RGB32, luz fixa em coordenadas da câmera, supersampling 2. Angulada 35°/20°; frontal/laterais com ambas arcadas, Up apenas superior, Inferior apenas inferior. Constantes próprias definidas antes dos folds, sem ajuste às imagens antigas. A lateralidade clínica não foi certificada.','', '## Validação e IC95%','', 'Cada conteúdo recebe predições apenas do modelo que não o usou no treino. Accuracy, erro ordinal e troca são agregados primeiro por conteúdo, preservando os dois sinais ou os 20 ensaios realistas. F1 macro é métrica do conjunto, recalculada da matriz de confusão; não existe F1 confiável para uma única pessoa. Bootstrap percentil: 10.000 reamostragens de conteúdos, mantendo todas as medidas repetidas de cada conteúdo juntas. IC condiciona às predições OOF fixas, sem retreino em cada bootstrap.','', '| Modelo substituto / baseline | Acurácia canônica (IC95%) | F1 macro | Erro ordinal grupo |','|---|---:|---:|---:|']
 for r in canonical:lines.append(f"| {r['modelo']} | {100*r['acuracia']:.1f}% ({100*r['acuracia_IC95_inf']:.1f}–{100*r['acuracia_IC95_sup']:.1f}) | {r['f1_macro']:.3f} | {r['erro_ordinal_grupo']:.3f} |")
 lines+=['','## Perturbações','', 'Rotações controladas: 2°, 3°, 5°, 10°, 20°, sinais ±, cada eixo separado, sobre o centro combinado canônico; mesma transformação nas duas arcadas. As rotações canônicas são conjugadas para as coordenadas STL nativas apenas para definir a perturbação física; os registradores recebem somente pontos, sem ângulo conhecido nem rótulo. Sem normalização, renderiza-se a pose canônica perturbada. Após normalização, o resultado é convertido ao referencial canônico congelado. O controle é PCA combinado + quatro sinais próprios + ICP; anatômica e multi5 usam o código/banco anterior, sem seleção nova.','', 'Realistas: mesmos 20 ensaios locais das etapas anteriores, com rotação SO(3), translação ±100, nova amostragem, ruído gaussiano sigma 0,15, recorte regional 10–30% e decimação. **Ruído e recorte atingem as nuvens de registro; a renderização usa a malha decimada íntegra.** Logo, esta análise realista mede principalmente a influência dessas alterações sobre a pose estimada, mais a decimação visível; não equivale a renderizar uma superfície com buracos ou ruído reconstruídos. A condição sem normalização conserva a translação, sem reenquadramento; vistas vazias são contabilizadas.','', 'A taxa de troca usa sempre a predição canônica do próprio modelo como referência, inclusive quando outro normalizador é aplicado. Portanto, troca entre modelos não equivale a melhora de acurácia. As condições sem normalização realista incluem translação/rotação muito maiores que o ensaio controlado.','', '| Modelo substituto / baseline | Normalização realista | Acurácia | Troca |','|---|---|---:|---:|']
 for r in real:lines.append(f"| {r['modelo']} | {r['normalizacao']} | {100*r['acuracia']:.1f}% | {100*r['taxa_troca']:.1f}% |")
 lines+=['','## Limiar empírico e resíduos','', 'O limiar é o primeiro ângulo **testado** cuja troca é estritamente maior que 5% ou 10%; não há interpolação nem garantia para ângulos intermediários. Os limiares por eixo, normalizador e ablation estão em `limiares_tolerancia.csv`. Um modelo que sempre prevê a mesma classe pode ter troca zero e baixa utilidade; consultar a acurácia e F1 junto com a tolerância.','']
 for r in thresholds:
  if r['modelo'].startswith('substituto_') and r['normalizacao']=='nenhuma' and r['eixo']=='todos':lines.append(f"- {r['modelo']}: >5% em {r['primeiro_angulo_troca_maior_5']}; >10% em {r['primeiro_angulo_troca_maior_10']}.")
 lines+=['','Resíduos geométricos realistas são relativos à normalização não perturbada de **cada método**, não à anatomia verdadeira nem à identidade do template:','']
 for p in pose:lines.append(f"- {p['metodo']}: mediana {p['mediana_graus']:.2f}°, IQR {p['Q25']:.2f}–{p['Q75']:.2f}°, máximo {p['maximo']:.2f}°, >5° em {100*p['taxa_maior_5']:.1f}%.")
 lines+=['','Comparar apenas o módulo angular residual com o limiar ignora eixo, sinal, translação e morfologia; é referência descritiva, não prova de tolerância.','', '## Limitações e arquivos','', 'O banco geométrico multi5 é global e previamente congelado, com P016/P004/P045/P029/P002. Esses conteúdos podem estar no teste da CV; assim, a validação não é independente para a cadeia completa. `sensibilidade_sem_templates.csv` exclui os cinco conteúdos-template somente da pontuação (sem retreino); ainda não remove a exposição geométrica anterior do normalizador. Não houve uso de rótulos para normalizar.','', 'O teste utiliza os mesmos conteúdos com perturbações, não novos pacientes capturados independentemente. Há poucos conteúdos, rótulos não auditados, nenhuma otimização de hiperparâmetros e apenas uma seed de treino por fold/variante; os IC não incluem toda a variabilidade de retreino. Consistência geométrica não certifica correção anatômica. Nenhum resultado se aplica ao Goslon AI.','', '- `metricas_IC95.csv`: todas as condições, IC95 de todas as métricas.','- `metricas_por_paciente.csv`: medidas por conteúdo-paciente.','- `predicoes_oof.csv`: predições individuais e resíduos, somente IDs.','- `matrizes_confusao.csv`: cada condição, contagens equivalentes de conteúdos.','- `diferencas_pareadas_IC95.csv`: ablations − canônico, diferenças pareadas.','- `residuos_pose.json` e `residuo_paciente_*.csv`: erro geométrico.','- `checkpoints/`: 15 cabeças substitutas; backbone público congelado.','- `features/`: embeddings e descritores reproduzíveis, sem nome de pasta de paciente.','- `folha_10_IDs.png`, `tolerancia_pose.png`, `normalizacao_pose.png`: revisão visual.','', 'Reprodução local: `../etapa1/.venv/bin/python experimento.py --workers 4` e `../etapa1/.venv/bin/python avaliar.py`, executados de etapa7b/ ou ajustando o caminho do executável. A preparação recusa sobrescrever um protocolo já congelado.']
 (OUT/'README.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':
 freeze_check();start=time.monotonic()
 if (OUT/'predicoes_oof.csv').exists():
  rows=list(csv.DictReader((OUT/'predicoes_oof.csv').open()));units=load(OUT/'unidades.json')
  for r in rows:
   for k in ['angle','pose_error_deg','rmse']:r[k]=float(r[k])
   for k in ['fold','grupo_real','predicao','troca','erro_ordinal','template_bank_content']:r[k]=int(r[k])
 else:rows,units=training()
 summaries,thresholds,pose=metrics(rows,units);figures(summaries,pose);readme(summaries,thresholds,pose);freeze_check();save('status.json',{'rotulo':'MODELO SUBSTITUTO','status':'CONCLUIDO','Goslon_AI':'NÃO AVALIADO','five_class':'NÃO EXECUTADO: classe 5 com menos de cinco conteúdos','seconds_analysis':time.monotonic()-start,'OOF_rows':len(rows),'unique_contents':len(units),'frozen_protocol_hashes_verified':True});print('MODELO SUBSTITUTO: avaliação e relatórios concluídos',flush=True)
