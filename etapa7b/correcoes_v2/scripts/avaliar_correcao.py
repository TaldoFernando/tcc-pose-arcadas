"""Avaliação local da extensão; não altera/reseleciona as cabeças congeladas."""
import os
for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:os.environ[k]="1"
from pathlib import Path
import sys,json,csv,collections,hashlib,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OLD=ROOT/"etapa7b";OUT=OLD/"correcoes_v2";RESULT=OUT/"resultados";SEED=20261121;B=10000
BANK={"P016","P004","P045","P029","P002"}
def load(p):return json.loads(Path(p).read_text())
def read(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,obj):(RESULT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def write(name,rows):
 with (RESULT/name).open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def original_rows():
 rows=read(OLD/"predicoes_oof.csv")
 for r in rows:
  for k in ["angle","pose_error_deg","rmse"]:r[k]=float(r[k])
  for k in ["fold","grupo_real","predicao","predicao_canonica","troca","acerto","erro_ordinal","template_bank_content","empty_views"]:r[k]=int(r[k])
 return rows

def audit_labels():
 pairs=load(ROOT/"etapa5/pares_ids.json");labels={r["ID"]:r for r in read(ROOT/"etapa5/rotulos_local.csv")};blocks=collections.defaultdict(list)
 for p in pairs:blocks[(p["superior"]["sha256"],p["inferior"]["sha256"])].append(p["id"])
 rows=[];perid=[]
 for ids in sorted(blocks.values(),key=lambda x:min(x)):
  ids=sorted(ids);groups={labels[i]["grupo"] for i in ids};goslon={labels[i]["goslon"] for i in ids};gc=len(groups)>1;sc=len(goslon)>1
  rows.append({"ID_conteudo":ids[0],"IDs":";".join(ids),"n_IDs":len(ids),"grupos":";".join(sorted(groups)),"GOSLON":";".join(sorted(goslon)),"conflito_grupo":gc,"conflito_GOSLON":sc,"rotulos_por_ID":json.dumps([{"ID":i,"grupo":labels[i]["grupo"],"GOSLON":labels[i]["goslon"]} for i in ids])})
  for i in ids:perid.append({"ID":i,"ID_conteudo":ids[0],"grupo":labels[i]["grupo"],"GOSLON":labels[i]["goslon"],"conflito_grupo":gc,"conflito_GOSLON":sc,"fonte":"nome da pasta"})
 write("auditoria_conteudos.csv",rows);write("rotulos_por_ID.csv",perid);write("divergencias_rotulos.csv",[r for r in rows if r["conflito_grupo"] or r["conflito_GOSLON"]])
 stats={"IDs":len(perid),"conteudos":len(rows),"conteudos_com_conflito_grupo":sum(r["conflito_grupo"] for r in rows),"conteudos_com_conflito_GOSLON":sum(r["conflito_GOSLON"] for r in rows),"conteudos_com_qualquer_conflito":sum(r["conflito_grupo"] or r["conflito_GOSLON"] for r in rows),"IDs_nesses_conteudos":sum(r["n_IDs"] for r in rows if r["conflito_grupo"] or r["conflito_GOSLON"]),"ressalva":"Conflito entre aliases nao e a mesma coisa que incompatibilidade presumida grupo x GOSLON; nenhum rotulo corrigido."}
 save("rotulos_resumo.json",stats);return rows

def predict_new(original,units):
 import torch
 from torch import nn
 from sklearn.pipeline import make_pipeline
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 class Head(nn.Sequential):
  def __init__(self):super().__init__(nn.LayerNorm(3456),nn.Linear(3456,64),nn.GELU(),nn.Dropout(.2),nn.Linear(64,3))
 canonical={(r["ID"],r["model"]):r["predicao"] for r in original if r["condition"]=="canonical"}
 data={};oldcanonical={}
 for u in units:
  identifier=u["ID"];z=np.load(OUT/"features"/f"{identifier}.npz");records=json.loads(str(z["records"]));data[identifier]={"x":z["features"].reshape(len(records),-1),"d":z["descriptors"],"records":records}
  z0=np.load(OLD/"features"/f"{identifier}.npz");oldcanonical[identifier]=(z0["features"][0].reshape(-1),z0["descriptors"][0])
 rows=[];checks=[]
 for fold in range(5):
  train=[u for u in units if u["fold"]!=fold];test=[u for u in units if u["fold"]==fold];y=np.array([u["grupo"]-1 for u in train]);major=int(np.argmax(np.bincount(y,minlength=3)))
  logistic=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,class_weight="balanced",random_state=20261106+fold));logistic.fit(np.stack([oldcanonical[u["ID"]][1] for u in train]),y)
  heads={}
  for model in ["substituto_canonico","substituto_aug10","substituto_aug20"]:
   cp=torch.load(OLD/"checkpoints"/f"{model}_fold{fold}.pt",map_location="cpu",weights_only=True)
   assert set(cp["train_IDs"])=={u["ID"] for u in train} and set(cp["test_IDs"])=={u["ID"] for u in test}
   net=Head();net.load_state_dict(cp["state_dict"]);heads[model]=net.eval()
  for u in test:
   identifier=u["ID"];d=data[identifier];pred={"majoritaria":np.full(len(d["records"]),major),"logistica_descritores":logistic.predict(d["d"])}
   reproduced={"majoritaria":major+1,"logistica_descritores":int(logistic.predict(oldcanonical[identifier][1][None,:])[0])+1}
   with torch.inference_mode():
    for model,net in heads.items():
     pred[model]=net(torch.tensor(d["x"])).argmax(1).numpy();reproduced[model]=int(net(torch.tensor(oldcanonical[identifier][0][None,:])).argmax(1)[0])+1
   assert all(reproduced[m]==canonical[identifier,m] for m in reproduced),"Referencia congelada divergiu"
   checks.append({"ID":identifier,"fold":fold,"cinco_predicoes_canonicas_reproduzidas":True,"cabecas_retreinadas":False})
   for model,pp in pred.items():
    centered0=int(pp[0])+1
    for j,r in enumerate(d["records"]):
     p=int(pp[j])+1;ref=canonical[identifier,model];rows.append(dict(r,rotulo="modelo substituto",model=model,fold=fold,grupo_real=u["grupo"],predicao=p,predicao_canonica=ref,predicao_centrada_0=centered0,acerto=int(p==u["grupo"]),erro_ordinal=abs(p-u["grupo"]),troca=int(p!=ref),troca_vs_zero_do_ramo=int(p!=centered0),template_bank_content=int(bool(set(u["aliases"])&BANK))))
 write("predicoes_centralizado.csv",rows);write("verificacao_modelos.csv",checks);return rows

def summarize(original,new,units):
 allrows=original+new;lookup={u["ID"]:u for u in units};baseids=sorted(lookup);assert len(baseids)==63
 exclude={u["ID"] for u in units if set(u["aliases"])&BANK};assert len(exclude)==5
 weightcache={};summaries=[];patient=[];cells=collections.defaultdict(list);stats_cache={}
 for r in allrows:
  assert r["ID"] in lookup
  key=(r["model"],r["condition"],r["method"],r["axis"],float(r["angle"]));cells[key].append(r)
  if r["condition"]=="rotation":cells[(r["model"],r["condition"],r["method"],"todos",float(r["angle"]))].append(r)
 def weights(ids):
  key=tuple(ids)
  if key not in weightcache:weightcache[key]=np.random.default_rng(SEED).multinomial(len(ids),[1/len(ids)]*len(ids),size=B).astype(float)/len(ids)
  return weightcache[key]
 def metrics(s):
  cm=s[...,:9].reshape(s.shape[:-1]+(3,3));tp=np.diagonal(cm,axis1=-2,axis2=-1);den=cm.sum(-1)+cm.sum(-2);f1=np.divide(2*tp,den,out=np.zeros_like(tp),where=den>0).mean(-1)
  return np.stack([tp.sum(-1),f1,s[...,9],s[...,10]],axis=-1)
 for key,rs in sorted(cells.items()):
  model,condition,method,axis,angle=key
  for pop,allowed in [("todos_63",set(baseids)),("sem_templates_58",set(baseids)-exclude)]:
   rr=[r for r in rs if r["ID"] in allowed];ids=sorted({r["ID"] for r in rr});assert set(ids)==allowed
   mat=np.zeros((len(ids),11));index={i:k for k,i in enumerate(ids)};counts=np.zeros(len(ids),int)
   for r in rr:
    j=index[r["ID"]];counts[j]+=1;mat[j,(r["grupo_real"]-1)*3+r["predicao"]-1]+=1;mat[j,9]+=r["erro_ordinal"];mat[j,10]+=r["troca"]
   mat/=counts[:,None];point=metrics(mat.mean(0));ci=np.quantile(metrics(weights(ids)@mat),[.025,.975],axis=0)
   base={"rotulo":"modelo substituto","populacao":pop,"modelo":model,"condicao":condition,"normalizacao":method,"eixo":axis,"angulo":angle,"n_conteudos":len(ids),"n_ensaios":len(rr),"unidade":"conteudo-paciente","carater":"exploratorio"}
   row=base.copy()
   for j,k in enumerate(["acuracia","f1_macro","erro_ordinal_grupo","taxa_troca"]):row[k]=float(point[j]);row[k+"_IC95_inf"]=float(ci[0,j]);row[k+"_IC95_sup"]=float(ci[1,j])
   summaries.append(row);stats_cache[(pop,)+key]=(ids,mat)
   for j,i in enumerate(ids):patient.append(dict(base,ID=i,n_repeticoes=int(counts[j]),grupo=lookup[i]["grupo"],acuracia=float(np.trace(mat[j,:9].reshape(3,3))),erro_ordinal_grupo=float(mat[j,9]),taxa_troca=float(mat[j,10])))
 write("metricas_IC95.csv",summaries);write("metricas_por_conteudo.csv",patient)
 contrasts=[]
 for pop in ["todos_63","sem_templates_58"]:
  for model in ["majoritaria","logistica_descritores","substituto_canonico","substituto_aug10","substituto_aug20"]:
   for cond,axis,angle in [("realistic","nenhum",0.)]+[("rotation",a,float(d)) for a in ["todos","vertical","anteroposterior","lateral"] for d in [2,3,5,10,20]]:
    for method,reference in [("centralizado","nenhuma"),("controle","centralizado"),("anatomica","centralizado"),("multi5_rmse","centralizado"),("multi5_rmse","nenhuma")]:
     ids,a=stats_cache[(pop,model,cond,method,axis,angle)];ids2,b=stats_cache[(pop,model,cond,reference,axis,angle)];assert ids==ids2
     # Diferenças lineares por conteúdo; F1 requer matriz do conjunto.
     vals=np.column_stack([np.trace(a[:,:9].reshape(-1,3,3),axis1=1,axis2=2)-np.trace(b[:,:9].reshape(-1,3,3),axis1=1,axis2=2),a[:,9]-b[:,9],a[:,10]-b[:,10]])
     est=vals.mean(0);ci=np.quantile(weights(ids)@vals,[.025,.975],axis=0)
     for j,metric in enumerate(["acuracia","erro_ordinal_grupo","taxa_troca"]):
      primary=pop=="sem_templates_58" and model=="substituto_canonico" and cond=="realistic" and method=="multi5_rmse" and reference=="centralizado" and metric=="taxa_troca"
      contrasts.append({"rotulo":"modelo substituto","populacao":pop,"modelo":model,"condicao":cond,"metodo":method,"referencia":reference,"eixo":axis,"angulo":angle,"metrica":metric,"diferenca":float(est[j]),"IC95_inf":float(ci[0,j]),"IC95_sup":float(ci[1,j]),"n_conteudos":len(ids),"unidade_estimando":"conteudo-paciente","unidade_bootstrap":"conteudo-paciente pareado","carater":"primario_da_extensao" if primary else "exploratorio"})
 write("contrastes_pareados_IC95.csv",contrasts)
 primary=[r for r in contrasts if r["carater"]=="primario_da_extensao"];assert len(primary)==1;save("desfecho_primario.json",primary[0])
 # Sensibilidade comparável em todas as condições: 58 menos 63, sem fingir amostras independentes.
 sensitivity=[];bykey={(r["populacao"],r["modelo"],r["condicao"],r["normalizacao"],r["eixo"],r["angulo"]):r for r in summaries}
 for r in summaries:
  if r["populacao"]!="todos_63":continue
  q=bykey[("sem_templates_58",r["modelo"],r["condicao"],r["normalizacao"],r["eixo"],r["angulo"])]
  for metric in ["acuracia","f1_macro","erro_ordinal_grupo","taxa_troca"]:
   sensitivity.append({"rotulo":"modelo substituto","modelo":r["modelo"],"condicao":r["condicao"],"normalizacao":r["normalizacao"],"eixo":r["eixo"],"angulo":r["angulo"],"metrica":metric,"estimativa_63":r[metric],"IC95_63_inf":r[metric+"_IC95_inf"],"IC95_63_sup":r[metric+"_IC95_sup"],"estimativa_58":q[metric],"IC95_58_inf":q[metric+"_IC95_inf"],"IC95_58_sup":q[metric+"_IC95_sup"],"diferenca_descritiva_58_menos_63":q[metric]-r[metric],"nota":"Populacoes aninhadas, diferenca de composicao; nao e ensaio de remover exposicao geometrica nem contraste independente."})
 write("sensibilidade_templates_todas_condicoes.csv",sensitivity)
 # Estratos, unidade sempre conteúdo; não calcular F1 dentro de uma única classe real.
 groups=[]
 for key,rr in collections_group(patient,["populacao","modelo","condicao","normalizacao","eixo","angulo","grupo"]).items():
  if key[2] not in ["canonical","realistic"]:continue
  ids=sorted(r["ID"] for r in rr);rby={r["ID"]:r for r in rr};values=np.array([[rby[i][k] for k in ["acuracia","erro_ordinal_grupo","taxa_troca"]] for i in ids]);ci=np.quantile(weights(ids)@values,[.025,.975],axis=0)
  row=dict(zip(["populacao","modelo","condicao","normalizacao","eixo","angulo","grupo"],key),n_conteudos=len(ids),unidade="conteudo-paciente",carater="exploratorio")
  for j,k in enumerate(["acuracia","erro_ordinal_grupo","taxa_troca"]):row[k]=float(values[:,j].mean());row[k+"_IC95_inf"]=float(ci[0,j]);row[k+"_IC95_sup"]=float(ci[1,j])
  groups.append(row)
 write("metricas_por_grupo_IC95.csv",groups)
 # Proporções geométricas corretamente rotuladas; nenhuma equivalência com erro clínico.
 geom=[];bygeom=collections_group([r for r in allrows if r["model"]=="substituto_canonico" and r["condition"]=="realistic"],["method","ID"])
 for (method,i),rr in bygeom.items():
  e=np.array([r["pose_error_deg"] for r in rr]);row={"ID":i,"metodo":method,"n_ensaios":len(e),"mediana_erro_consistencia_pose_graus":float(np.median(e)),"nota":"Referencia do proprio metodo; nao falha anatomica ou classificatoria."}
  for t in [2,3,5,10]:row[f"proporcao_erro_consistencia_pose_maior_{t}_graus"]=float((e>t).mean())
  geom.append(row)
 write("residuos_pose_por_conteudo.csv",geom)
 framing=[]
 for method in ["nenhuma","centralizado","controle","anatomica","multi5_rmse"]:
  rr=[r for r in allrows if r["model"]=="substituto_canonico" and r["condition"]=="realistic" and r["method"]==method]
  framing.append({"normalizacao":method,"n_conteudos":len({r["ID"] for r in rr}),"n_condicoes":len(rr),"n_vistas":6*len(rr),"vistas_vazias":sum(r["empty_views"] for r in rr),"fracao_vazias":sum(r["empty_views"] for r in rr)/(6*len(rr))})
 write("enquadramento_realista.csv",framing)
 # Contraste secundário de rotação com referência do próprio ramo centralizado em 0°.
 own=[]
 for (model,identifier,axis,deg),rr in collections_group([r for r in new if r["condition"]=="rotation"],["model","ID","axis","angle"]).items():own.append({"modelo":model,"ID":identifier,"eixo":axis,"angulo":deg,"taxa_troca_vs_zero_centralizado":float(np.mean([r["troca_vs_zero_do_ramo"] for r in rr])),"unidade":"conteudo-paciente","carater":"exploratorio"})
 write("rotacoes_referencia_proprio_ramo.csv",own)
 return summaries,contrasts,framing

def collections_group(rows,keys):
 d=collections.defaultdict(list)
 for r in rows:d[tuple(r[k] for k in keys)].append(r)
 return d

def main():
 freeze=load(OUT/"congelamento_analise.json")
 for name,digest in freeze["files"].items():assert sha(ROOT/name)==digest,name
 original=original_rows();units=load(OLD/"unidades.json");audit_labels();new=predict_new(original,units);summaries,contrasts,framing=summarize(original,new,units)
 save("status.json",{"rotulo":"modelo substituto","status":"CONCLUIDO","novas_predicoes":len(new),"conteudos":len(units),"banco_por_fold":"NAO_REFEITO; sensibilidade 58/63 em todas as condicoes","originais_preservados":True,"cabecas_retreinadas":False,"sem_envio_externo":True})
 print(json.dumps({"status":"CONCLUIDO","novas_predicoes":len(new),"metricas":len(summaries),"contrastes":len(contrasts)}),flush=True)
if __name__=="__main__":main()
