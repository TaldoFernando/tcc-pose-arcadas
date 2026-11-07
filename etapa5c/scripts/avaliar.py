"""Bootstrap de pacientes proxy; repetições/folds são medidas no mesmo bloco."""
import os
for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:os.environ[k]="1"
from pathlib import Path
import json,csv,collections
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa5c";B=10000;SEED=20261300;WEIGHTS={}
def load(p):return json.loads(Path(p).read_text())
def read(p):return list(csv.DictReader(Path(p).open()))
def write(n,rows):
 with (OUT/n).open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def weights(ids):
 key=tuple(ids)
 if key not in WEIGHTS:WEIGHTS[key]=np.random.default_rng(SEED).multinomial(len(ids),[1/len(ids)]*len(ids),size=B)/len(ids)
 return WEIGHTS[key]
def stat(s):
 cm=s[...,:9].reshape(s.shape[:-1]+(3,3));tp=np.diagonal(cm,axis1=-2,axis2=-1);den=cm.sum(-1)+cm.sum(-2);f1=np.divide(2*tp,den,out=np.zeros_like(tp),where=den>0).mean(-1)
 return np.stack([tp.sum(-1),f1,s[...,9],s[...,10]],axis=-1)
def aggregate(rs):
 byid=collections.defaultdict(list)
 for r in rs:byid[r["ID"]].append(r)
 blocks=collections.defaultdict(list);counts={}
 for i,rr in byid.items():
  s=np.zeros(11)
  for r in rr:s[(int(r["grupo_real"])-1)*3+int(r["predicao"])-1]+=1;s[9]+=float(r["erro_ordinal_grupo"]);s[10]+=float(r["troca"])
  blocks[rr[0]["bloco_paciente_proxy"]].append(s/len(rr));counts[i]=len(rr)
 ids=sorted(blocks);mat=np.stack([np.mean(blocks[i],axis=0) for i in ids]);point=stat(mat.mean(0));ci=np.quantile(stat(weights(ids)@mat),[.025,.975],axis=0)
 return ids,mat,point,ci,counts
def main():
 rows=read(OUT/"resultados/predicoes_OOF.csv");dev=load(OUT/"desenvolvimento.json");bank={"P016","P004","P045","P029","P002"};bankblocks={c["bloco_paciente_proxy"] for c in dev if set(c["aliases"])&bank};cells=collections.defaultdict(list)
 for r in rows:
  key=(r["modelo"],r["condicao"],r["normalizacao"],r["eixo"],float(r["angulo"]));cells[key].append(r)
  if r["condicao"]=="rotation":cells[(r["modelo"],r["condicao"],r["normalizacao"],"todos",float(r["angulo"]))].append(r)
 summaries=[];cache={};individual=[]
 for key,rs in sorted(cells.items()):
  model,cond,method,axis,angle=key
  for population in ["desenvolvimento_completo","sensibilidade_sem_banco"]:
   rr=rs if population=="desenvolvimento_completo" else [r for r in rs if r["bloco_paciente_proxy"] not in bankblocks]
   ids,mat,point,ci,counts=aggregate(rr)
   base={"rotulo":"modelo substituto","populacao":population,"modelo":model,"condicao":cond,"normalizacao":method,"eixo":axis,"angulo":angle,"n_blocos_paciente_proxy":len(ids),"n_conteudos":len(counts),"repeticoes_CV":5,"unidade":"paciente proxy, nao identidade clinica confirmada","carater":"exploratorio"};row=base.copy()
   for j,k in enumerate(["acuracia","f1_macro","erro_ordinal_grupo","taxa_troca"]):row[k]=float(point[j]);row[k+"_IC95_inf"]=float(ci[0,j]);row[k+"_IC95_sup"]=float(ci[1,j])
   summaries.append(row);cache[(population,)+key]=(ids,mat)
   for i,s in zip(ids,mat):individual.append(dict(base,bloco_paciente_proxy=i,acuracia=float(np.trace(s[:9].reshape(3,3))),erro_ordinal_grupo=float(s[9]),taxa_troca=float(s[10])))
 write("resultados/metricas_OOF_IC95.csv",summaries);write("resultados/resumos_por_paciente_proxy.csv",individual)
 contrasts=[]
 for population in ["desenvolvimento_completo","sensibilidade_sem_banco"]:
  for model in ["substituto_canonico","logistica_descritores","majoritaria"]:
   for m,ref in [("centralizado","nenhuma"),("multi5_rmse","centralizado"),("controle","centralizado"),("anatomica","centralizado")]:
    ids,a=cache[(population,model,"realistic",m,"nenhum",0.)];ids2,b=cache[(population,model,"realistic",ref,"nenhum",0.)];assert ids==ids2
    d=np.column_stack([np.trace(a[:,:9].reshape(-1,3,3),axis1=1,axis2=2)-np.trace(b[:,:9].reshape(-1,3,3),axis1=1,axis2=2),a[:,9]-b[:,9],a[:,10]-b[:,10]]);ci=np.quantile(weights(ids)@d,[.025,.975],axis=0)
    for j,metric in enumerate(["acuracia","erro_ordinal_grupo","taxa_troca"]):contrasts.append({"populacao":population,"modelo":model,"condicao":"realistic","metodo":m,"referencia":ref,"metrica":metric,"diferenca":float(d[:,j].mean()),"IC95_inf":float(ci[0,j]),"IC95_sup":float(ci[1,j]),"n_pacientes_proxy":len(ids),"unidade_bootstrap":"paciente proxy pareado","carater":"exploratorio"})
 write("resultados/contrastes_OOF_IC95.csv",contrasts)
 thresholds=[]
 for population in ["desenvolvimento_completo","sensibilidade_sem_banco"]:
  for model in ["substituto_canonico","logistica_descritores","majoritaria"]:
   for method in ["nenhuma","centralizado","controle","anatomica","multi5_rmse"]:
    for axis in ["todos","vertical","anteroposterior","lateral"]:
     rr=sorted([r for r in summaries if r["populacao"]==population and r["modelo"]==model and r["condicao"]=="rotation" and r["normalizacao"]==method and r["eixo"]==axis],key=lambda r:r["angulo"]);zero_measured=method in ["nenhuma","centralizado","multi5_rmse"]
     if zero_measured:
      zero=next(r for r in summaries if r["populacao"]==population and r["modelo"]==model and r["condicao"]=="canonical" and r["normalizacao"]==("centralizado" if method=="centralizado" else "referencia_canonica_multi5"));rr=[dict(zero,angulo=0.)]+rr
     thresholds.append({"populacao":population,"modelo":model,"normalizacao":method,"eixo":axis,"primeiro_angulo_troca_maior_5_pct":next((r["angulo"] for r in rr if r["taxa_troca"]>.05),"nao excedeu nos angulos avaliados"),"primeiro_angulo_troca_maior_10_pct":next((r["angulo"] for r in rr if r["taxa_troca"]>.10),"nao excedeu nos angulos avaliados"),"zero_ramo_medido":zero_measured,"carater":"exploratorio","ressalva":"Referencia canonica multi5 comum; mudar normalizador/enquadramento pode alterar classe sem rotacao; sem interpolacao."})
 write("resultados/tolerancia_OOF.csv",thresholds)
 repeat=[]
 for model in ["substituto_canonico","logistica_descritores","majoritaria"]:
  for rep in range(5):
   rr=[r for r in rows if r["modelo"]==model and r["repeticao"]==str(rep) and r["condicao"]=="canonical" and r["normalizacao"]=="referencia_canonica_multi5"];ids,mat,point,ci,_=aggregate(rr)
   repeat.append({"modelo":model,"repeticao":rep,"n_pacientes_proxy":len(ids),"acuracia":float(point[0]),"F1_macro":float(point[1]),"erro_ordinal_grupo":float(point[2]),"nota":"Repeticoes sobrepostas; nao 5 amostras independentes."})
 write("resultados/metricas_por_repeticao.csv",repeat)
 write("resultados/exclusoes_sensibilidade_banco.csv",[{"ID":c["ID"],"bloco_paciente_proxy":c["bloco_paciente_proxy"],"motivo":"template ou bloco geometrico do template"} for c in dev if c["bloco_paciente_proxy"] in bankblocks])
 (OUT/"resultados/status_analise_OOF.json").write_text(json.dumps({"status":"CONCLUIDO","test_features_or_predictions_used":False,"n_metricas":len(summaries),"n_predicoes_OOF":len(rows),"n_contrastes":len(contrasts),"unidade":"paciente proxy","bootstrap_retreina_modelos":False},indent=2)+"\n")
 print("OOF e bootstrap concluidos; teste continua bloqueado.",flush=True)
if __name__=="__main__":main()
