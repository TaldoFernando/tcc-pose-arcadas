"""Congela o protocolo do modelo substituto antes de qualquer ajuste supervisionado."""
from pathlib import Path
import collections,csv,hashlib,json,sys,time
import numpy as np
from sklearn.model_selection import StratifiedKFold
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa7b';SEED=20261106
def save(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False))
def csvsave(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if __name__=='__main__':
 if (OUT/'congelamento.json').exists():raise SystemExit('Protocolo já congelado; não sobrescrever.')
 pairs=json.loads((ROOT/'etapa5/pares_ids.json').read_text());labels={r['ID']:r for r in csv.DictReader((ROOT/'etapa5/rotulos_local.csv').open())};content=collections.defaultdict(list)
 for p in pairs:content[p['superior']['sha256']+'|'+p['inferior']['sha256']].append(p['id'])
 units=[];audit=[];counts={}
 for field in ['grupo','goslon']:
  c=collections.Counter()
  for ids in content.values():
   values={labels[i][field] for i in ids}
   if len(values)==1:c[next(iter(values))]+=1
  counts[field]=dict(c)
 for key,ids in content.items():
  ids=sorted(ids);groups={labels[i]['grupo'] for i in ids};gs={labels[i]['goslon'] for i in ids};eligible=len(groups)==1
  if eligible:units.append({'ID':ids[0],'aliases':ids,'grupo':int(next(iter(groups))),'goslon':int(next(iter(gs))) if len(gs)==1 else None,'conteudo_sha256':hashlib.sha256(key.encode()).hexdigest()})
  for i in ids:audit.append({'ID':i,'ID_conteudo':ids[0],'grupo':labels[i]['grupo'],'goslon':labels[i]['goslon'],'elegivel_3_grupos':eligible,'conflito_grupo':len(groups)>1,'conflito_goslon':len(gs)>1,'fold':-1})
 units.sort(key=lambda r:r['ID']);folds={}
 for fold,(_,test) in enumerate(StratifiedKFold(5,shuffle=True,random_state=SEED).split(units,[u['grupo'] for u in units])):
  for idx in test:units[idx]['fold']=fold;folds[units[idx]['ID']]=fold
 for r in audit:
  if r['elegivel_3_grupos']:r['fold']=folds[r['ID_conteudo']]
 csvsave('conteudos_folds.csv',audit);save('unidades.json',units);save('contagens.json',counts)
 cfg=json.loads((ROOT/'etapa6/camera_config.json').read_text())
 # Valores próprios redondos, fixados a priori: nenhum fitting nesta validação cruzada.
 cfg={k:cfg[k] for k in ['status','views','appearance','angle_definition','scale_units','model_base_treatment']}
 cfg.update({'purpose':'MODELO SUBSTITUTO: câmeras próprias; não reproduzem câmeras originais','legacy_training_cameras':'PLACEHOLDER','camera_selection':'constantes redondas a priori, sem otimização por imagens, classes ou folds','axes':{'lateral':[1,0,0],'anteroposterior':[0,1,0],'vertical':[0,0,1]},'normalization_model':'../etapa6/stl/modelo_normalizacao.npz'})
 for view,cam in cfg['views'].items():
  old=np.asarray(cam['position'])-np.asarray(cam['target']);cam['target']=[0.,0.,0.];cam['position']=(old/np.linalg.norm(old)*200).tolist();cam['ortho_height']=110.;cam['resolution']=[224,224];cam['parameter_status']='PRÓPRIO_CONGELADO_NÃO_CALIBRADO_AO_TREINO_ORIGINAL'
 save('camera_config_proprio.json',cfg)
 protocol={'rotulo':'MODELO SUBSTITUTO; nenhuma inferência sobre Goslon AI','seed':SEED,'folds':5,'unique_content_primary':len(units),'group_counts':counts['grupo'],'five_class':'NÃO EXECUTAR: classe GOSLON 5 tem somente quatro conteúdos únicos não conflitantes','group_conflict_policy':'excluir conteúdo de grupos conflitantes; um representante por conteúdo, aliases no mesmo fold','goslon_conflict_policy':'não converter grupo em GOSLON; conflito GOSLON não exclui grupo consistente','backbone':'torchvision MobileNet_V3_Small IMAGENET1K_V1; features + adaptive average pooling; 576 dimensões/vista; inteiramente congelado, eval; seis vistas concatenadas','head':{'input':3456,'layers':'LayerNorm(3456), Linear(3456,64), GELU, Dropout(0.2), Linear(64,3)','epochs':80,'batch_size':8,'optimizer':'AdamW','lr':0.001,'weight_decay':0.01,'loss':'CrossEntropy, pesos inversos à frequência apenas no treino','selection':'última época, sem early stopping, sem ajuste por teste','training_seed':'20261106 + 100*fold, idêntica entre as três variantes','paired_ablation':'mesma inicialização, dropout, ordem de minibatches e atualizações; RNG de augmentation separado','steps':'um exemplo por conteúdo/época, mesmo número de atualizações nas três variantes'},'augmentation':{'canonical':'nenhuma rotação','aug10':'probabilidade 0.5 canônica; senão uma de seis rotações 3D fixas por conteúdo, eixo sorteado e ângulo uniforme [-10,10]','aug20':'idem, limite 20 graus','seed':'20261106+5000+100*ID+limite','not_2d_rotation':True},'baseline_logistic':'StandardScaler + LogisticRegression(C=1,max_iter=2000,class_weight=balanced); 8 descritores por vista; treino somente canônico','baseline_majority':'classe mais frequente somente no treino; empate menor grupo','rotations':{'angles_deg':[2,3,5,10,20],'axes':['vertical','anteroposterior','lateral'],'signs':[-1,1],'center':'centroide combinado dos pontos canônicos; ambos arcos juntos'},'normalizers':['controle','anatomica','multi5_rmse'],'normalization_bank':['P016','P004','P045','P029','P002'],'normalization_refitting':'nenhum; código e banco congelados; grupo/rótulo nunca entra na normalização','realistic':{'trials_per_content':20,'source':'etapa5/clouds; mesmas seeds/reamostragem/ruído sigma 0.15/recorte regional 10–30%; malhas decimadas leve/forte','render_geometry':'decimação visível; ruído e recorte afetam as nuvens de registro; sem reconstrução inventada da superfície','none':'rotação SO(3) e translação originais, sem reenquadrar; imagens vazias contam como resultado'},'scoring':'previsões out-of-fold; referência de troca = condição canônica multi5 comum a todos os métodos; sinais/ensaios ponderados igualmente dentro de cada conteúdo; depois conteúdos com mesmo peso','bootstrap':{'replicates':10000,'unit':'conteúdo-paciente; mantém sinais/ensaios juntos','interval':'percentil 2.5/97.5; confusão reponderada por conteúdo, F1 macro calculado novamente','seed':SEED+90000},'thresholds':'primeiro ângulo testado com taxa de troca estritamente >5% ou >10%; sem interpolar; ângulo 0 incluído como referência','limitations':['rótulos extraídos de nomes, sem validação clínica','normalizador global previamente congelado contém templates que podem estar nos folds de teste; CV não independente para toda a cadeia','resultado geométrico consistente não significa anatomicamente correto','erro ordinal de grupos 1–3 não equivale a erro GOSLON 1–5','bootstrap de predições OOF fixas: não retreina redes nem inclui incerteza de escolha de pesos/seeds']}
 save('protocolo.json',protocol)
 weights=Path.home()/'.cache/torch/hub/checkpoints/mobilenet_v3_small-047dcff4.pth'
 freeze={'frozen_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'before_training':True,'files':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'protocolo.json',OUT/'camera_config_proprio.json',OUT/'conteudos_folds.csv',ROOT/'etapa6/stl/modelo_normalizacao.npz',ROOT/'etapa6/stl/transformacoes.json',ROOT/'etapa5/anatomical_pair.py',ROOT/'etapa5/pca_pair.py',ROOT/'etapa5/rigid_icp.py',OUT/'experimento.py',OUT/'avaliar.py']},'backbone':{'source':'https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth','sha256':sha(weights),'patient_data_sent':False}}
 save('congelamento.json',freeze);print('CONGELADO:',len(units),'conteúdos;',counts)
