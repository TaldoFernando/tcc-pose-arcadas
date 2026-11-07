"""Única abertura final: somente canônica, sem curvas de pose no teste."""
from pathlib import Path
import sys,json,csv,hashlib,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa5c"
from classificador import feature,predict,verify
from avaliar import aggregate,write
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 import torch
 from torch import nn
 verify();gate=OUT/"liberacao_final.json";assert gate.exists(),"Treinar/congelar modelo final antes de abrir teste"
 for n,h in load(gate)["files"].items():assert sha(ROOT/n)==h,n
 assert not (OUT/"teste_bloqueado/abertura.json").exists(),"Teste final ja aberto; nao repetir para selecionar resultados."
 # Primeira leitura dos rótulos deste payload pelo código de avaliação.
 (OUT/"teste_bloqueado/abertura.json").write_text(json.dumps({"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"sha256_liberacao_final":sha(gate),"scope":"somente canonica; sem ajuste ou escolha apos resultado"},indent=2)+"\n")
 test=load(OUT/"teste_bloqueado/entradas.json");split=load(OUT/"divisao.json");assert {c["ID"] for c in test}==set(split["test_IDs"])
 cp=torch.load(OUT/"checkpoints/modelo_final.pt",map_location="cpu",weights_only=True);assert set(cp["metadata"]["train_IDs"])==set(split["dev_IDs"])
 assert not set(cp["metadata"]["train_IDs"])&set(split["test_IDs"])
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 net=nn.Sequential(nn.LayerNorm(3456),nn.Linear(3456,64),nn.GELU(),nn.Dropout(.2),nn.Linear(64,3));net.load_state_dict(cp["state_dict"]);net.eval();base=load(OUT/"checkpoints/baselines_finais.json");rows=[]
 for c in test:
  data=feature(c["ID"],False);assert len(data["records"])==1
  for model,pp in predict(net,base,data).items():
   p=int(pp[0])+1;rows.append({"rotulo":"modelo substituto","ID":c["ID"],"bloco_paciente_proxy":c["bloco_paciente_proxy"],"modelo":model,"grupo_real":c["grupo"],"predicao":p,"condicao":"canonical","normalizacao":"referencia_canonica_multi5","acerto":int(p==c["grupo"]),"erro_ordinal_grupo":abs(p-c["grupo"]),"troca":0})
 write("resultados/predicoes_teste_final.csv",rows);summary=[];confusion=[];groups=[]
 for model in ["substituto_canonico","logistica_descritores","majoritaria"]:
  rr=[r for r in rows if r["modelo"]==model];ids,mat,point,ci,counts=aggregate(rr);r={"rotulo":"modelo substituto","modelo":model,"condicao":"canonical","n_pacientes_proxy":len(ids),"n_conteudos":len(counts),"unidade_bootstrap":"paciente proxy, sem repeticoes independentes","metrica_primaria":model=="substituto_canonico"}
  for j,k in enumerate(["acuracia","f1_macro","erro_ordinal_grupo"]):r[k]=float(point[j]);r[k+"_IC95_inf"]=float(ci[0,j]);r[k+"_IC95_sup"]=float(ci[1,j])
  summary.append(r);cm=mat[:,:9].sum(0).reshape(3,3)
  for y in range(3):
   for p in range(3):confusion.append({"modelo":model,"grupo_real":y+1,"predicao":p+1,"pacientes_proxy_equivalentes":float(cm[y,p])})
  for g in [1,2,3]:
   rs=[r for r in rr if r["grupo_real"]==g];ids,mat,est,ci,counts=aggregate(rs);q={"modelo":model,"grupo":g,"n_pacientes_proxy":len(ids),"n_conteudos":len(counts),"menos_5_pacientes_proxy":len(ids)<5,"carater":"exploratorio","F1_no_estrato":"NA; apenas uma classe real"}
   for j,k in [(0,"acuracia"),(2,"erro_ordinal_grupo")]:q[k]=float(est[j]);q[k+"_IC95_inf"]=float(ci[0,j]);q[k+"_IC95_sup"]=float(ci[1,j])
   groups.append(q)
 write("resultados/metricas_teste_final_IC95.csv",summary);write("resultados/confusao_teste_final.csv",confusion);write("resultados/metricas_grupo_teste_IC95.csv",groups)
 (OUT/"resultados/primario_teste.json").write_text(json.dumps(next(r for r in summary if r["modelo"]=="substituto_canonico"),indent=2)+"\n")
 (OUT/"resultados/status_teste_final.json").write_text(json.dumps({"status":"AVALIACAO_FINAL_CONCLUIDA","test_scope":"somente canonica","ajustes_apos_teste":False,"curvas_tolerancia_no_teste":False,"n_conteudos":len(test),"abertura_unica":True},indent=2)+"\n")
 print("Teste final avaliado uma vez, sem ajuste.",flush=True)
if __name__=="__main__":main()
