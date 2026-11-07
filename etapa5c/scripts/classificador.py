"""Cabeça substituta fixa; OOF só no desenvolvimento e teste em outra etapa."""
import os
for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:os.environ[k]="1"
from pathlib import Path
import json,csv,hashlib,datetime,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa5c"
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def verify():
 for manifest in ["congelamento.json","congelamento_execucao.json"]:
  for n,h in load(OUT/manifest)["files"].items():assert sha(ROOT/n)==h,n
def feature(identifier,all_conditions=True):
 z=np.load(ROOT/"etapa7b/features"/f"{identifier}.npz");records=json.loads(str(z["records"]));idx=[i for i,r in enumerate(records) if r["condition"]!="augmentation"] if all_conditions else [0]
 x=z["features"][idx].reshape(len(idx),-1);d=z["descriptors"][idx];rec=[records[i].copy() for i in idx]
 if all_conditions:
  z2=np.load(ROOT/"etapa7b/correcoes_v2/features"/f"{identifier}.npz");r2=json.loads(str(z2["records"]));x=np.concatenate([x,z2["features"].reshape(len(r2),-1)]);d=np.concatenate([d,z2["descriptors"]]);rec+=r2
 assert rec[0]["condition"]=="canonical" and rec[0]["method"]=="nenhuma"
 return {"x":np.ascontiguousarray(x),"d":d,"records":rec}
def fit(train,lookup,data,seed):
 import torch
 from torch import nn
 from sklearn.pipeline import make_pipeline
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True);torch.manual_seed(seed)
 y=np.array([lookup[i]["grupo"]-1 for i in train]);freq=np.bincount(y,minlength=3);assert (freq>0).all()
 logistic=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,class_weight="balanced",random_state=seed));logistic.fit(np.stack([data[i]["d"][0] for i in train]),y)
 net=nn.Sequential(nn.LayerNorm(3456),nn.Linear(3456,64),nn.GELU(),nn.Dropout(.2),nn.Linear(64,3))
 opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.01);lossfn=nn.CrossEntropyLoss(weight=torch.tensor(len(y)/(3*freq),dtype=torch.float32))
 x=torch.tensor(np.stack([data[i]["x"][0] for i in train]));target=torch.tensor(y,dtype=torch.long);rng=np.random.default_rng(seed)
 for epoch in range(80):
  order=rng.permutation(len(train));net.train()
  for start in range(0,len(train),8):
   k=order[start:start+8];opt.zero_grad();loss=lossfn(net(x[k]),target[k]);loss.backward();opt.step()
 net.eval();scaler=logistic[0];clf=logistic[1]
 base={"majoritaria":int(np.argmax(freq)),"mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),"coef":clf.coef_.tolist(),"intercept":clf.intercept_.tolist(),"classes":clf.classes_.tolist()}
 return net,base,{"seed":seed,"train_IDs":train,"epocas":80,"ultima_epoca":True,"treino_grupos":freq.tolist(),"loss_final":float(loss.detach()),"hyperparameters_selected_by_test":False}
def predict(net,base,data):
 import torch
 with torch.inference_mode():neural=net(torch.tensor(data["x"])).argmax(1).numpy()
 s=(data["d"]-np.array(base["mean"]))/np.array(base["scale"]);scores=s@np.array(base["coef"]).T+np.array(base["intercept"]);log=np.array(base["classes"])[scores.argmax(1)]
 return {"substituto_canonico":neural,"logistica_descritores":log,"majoritaria":np.full(len(neural),base["majoritaria"])}
def cv():
 import torch
 verify()
 if (OUT/"resultados/predicoes_OOF.csv").exists():raise SystemExit("OOF ja gerado; nao sobrescrever sem nova versao.")
 dev=load(OUT/"desenvolvimento.json");lookup={u["ID"]:u for u in dev};folds=load(OUT/"folds_CV.json");data={i:feature(i) for i in lookup};rows=[];logs=[]
 for f in folds:
  train=f["train_IDs"];val=f["val_IDs"];assert set(train)|set(val)==set(lookup) and not set(train)&set(val)
  assert not {lookup[i]["bloco_paciente_proxy"] for i in train}&{lookup[i]["bloco_paciente_proxy"] for i in val}
  seed=20261200+1000*f["repeticao"]+100*f["fold"];net,base,log=fit(train,lookup,data,seed)
  path=OUT/"checkpoints"/f"CV_r{f['repeticao']}_f{f['fold']}.pt";torch.save({"state_dict":net.state_dict(),"metadata":log},path)
  for i in val:
   prediction=predict(net,base,data[i]);meta=lookup[i]
   for model,pp in prediction.items():
    reference=int(pp[0])+1
    for j,r in enumerate(data[i]["records"]):
     p=int(pp[j])+1;method="referencia_canonica_multi5" if r["condition"]=="canonical" and r["method"]=="nenhuma" else r["method"]
     rows.append({"rotulo":"modelo substituto","ID":i,"bloco_paciente_proxy":meta["bloco_paciente_proxy"],"repeticao":f["repeticao"],"seed_divisao":f["seed"],"fold":f["fold"],"modelo":model,"grupo_real":meta["grupo"],"condicao":r["condition"],"normalizacao":method,"eixo":r["axis"],"angulo":float(r["angle"]),"sinal":r["sign"],"ensaio":r["trial"],"predicao":p,"predicao_canonica":reference,"acerto":int(p==meta["grupo"]),"erro_ordinal_grupo":abs(p-meta["grupo"]),"troca":int(p!=reference),"vistas_vazias":r["empty_views"]})
  logs.append(dict(log,repeticao=f["repeticao"],fold=f["fold"],val_IDs=val));print("OOF",f["repeticao"],f["fold"],"treino",len(train),"validacao",len(val),flush=True)
 with (OUT/"resultados/predicoes_OOF.csv").open("w",newline="") as file:w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save("resultados/treinamento_CV.json",logs);save("resultados/status_OOF.json",{"status":"OOF_CONCLUIDO","ajustes":20,"predicoes":len(rows),"n_conteudos":len(dev),"repeticoes":5,"test_labels_loaded":False,"test_features_loaded":False,"utc":now()})
def final_fit():
 import torch
 verify();assert (OUT/"resultados/metricas_OOF_IC95.csv").exists(),"Concluir OOF antes de congelar o ajuste final"
 if (OUT/"liberacao_final.json").exists():raise SystemExit("Ajuste final ja congelado.")
 dev=load(OUT/"desenvolvimento.json");lookup={u["ID"]:u for u in dev};data={i:feature(i,False) for i in lookup}
 net,base,log=fit(sorted(lookup),lookup,data,20261299)
 path=OUT/"checkpoints/modelo_final.pt";torch.save({"state_dict":net.state_dict(),"metadata":log},path);save("checkpoints/baselines_finais.json",base);save("resultados/treinamento_final.json",log)
 files=[path,OUT/"checkpoints/baselines_finais.json",OUT/"plano_previo.json",OUT/"divisao.json",OUT/"scripts/classificador.py",OUT/"scripts/teste_final.py",OUT/"resultados/metricas_OOF_IC95.csv",OUT/"resultados/treinamento_CV.json"]
 save("liberacao_final.json",{"utc":now(),"before_any_final_test_prediction":True,"no_test_used_for_choice":True,"model_choice":"arquitetura e hiperparametros fixados antes da CV; nenhuma escolha de vencedor por teste","test_scope":"apenas canonica, sem curvas de tolerancia","train_only_development_IDs":sorted(lookup),"files":{str(p.relative_to(ROOT)):sha(p) for p in files}})
 print("MODELO FINAL CONGELADO; teste ainda nao avaliado.",flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("mode",choices=["cv","final_fit"]);a=p.parse_args();(cv if a.mode=="cv" else final_fit)()
