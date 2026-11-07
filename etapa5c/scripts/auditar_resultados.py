"""Verificação independente de métricas e integridade dos STL; sem novas inferências."""
from pathlib import Path
import json,csv,hashlib,collections,datetime
import numpy as np
from sklearn.metrics import accuracy_score,f1_score,mean_absolute_error
ROOT=Path(__file__).resolve().parents[2];O=ROOT/"etapa5c";R=O/"resultados"
def read(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=read(R/"predicoes_teste_final.csv");summ=read(R/"metricas_teste_final_IC95.csv")
for s in summ:
 rr=[r for r in rows if r["modelo"]==s["modelo"]];y=[int(r["grupo_real"]) for r in rr];p=[int(r["predicao"]) for r in rr]
 expected=[accuracy_score(y,p),f1_score(y,p,labels=[1,2,3],average="macro",zero_division=0),mean_absolute_error(y,p)]
 for k,v in zip(["acuracia","f1_macro","erro_ordinal_grupo"],expected):assert np.isclose(float(s[k]),v),(s["modelo"],k)
oof=read(R/"predicoes_OOF.csv")
for s in read(R/"metricas_OOF_IC95.csv"):
 if s["condicao"]!="canonical" or s["normalizacao"]!="referencia_canonica_multi5" or s["populacao"]!="desenvolvimento_completo":continue
 rr=[r for r in oof if r["modelo"]==s["modelo"] and r["condicao"]=="canonical" and r["normalizacao"]=="referencia_canonica_multi5"]
 y=[int(r["grupo_real"]) for r in rr];p=[int(r["predicao"]) for r in rr]
 # Cada paciente tem exatamente cinco predições; peso igual aqui e no agregador.
 assert len(rr)==46*5 and set(collections.Counter(r["ID"] for r in rr).values())=={5}
 assert np.isclose(float(s["f1_macro"]),f1_score(y,p,labels=[1,2,3],average="macro",zero_division=0))
for filename in ["metricas_OOF_IC95.csv","metricas_teste_final_IC95.csv","metricas_grupo_teste_IC95.csv"]:
 for r in read(R/filename):
  for k,v in r.items():
   if k.endswith("_IC95_inf"):
    metric=k.removesuffix("_IC95_inf");low=float(v);high=float(r[metric+"_IC95_sup"]);assert low<=high
    assert low>=0 and (metric=="erro_ordinal_grupo" or high<=1)
# Comparação com os hashes registrados antes desta etapa, sem regravar malhas.
count=0
for pair in load(ROOT/"etapa5/pares_ids.json"):
 for arch in ["superior","inferior"]:
  m=pair[arch];assert sha(ROOT/"etapa5"/m["arquivo"])==m["sha256"],pair["id"];count+=1
assert not list(O.rglob("*.stl"))
freeze=load(O/"congelamento.json");exe=load(O/"congelamento_execucao.json");gate=load(O/"liberacao_final.json");opened=load(O/"teste_bloqueado/abertura.json")
ts=[datetime.datetime.fromisoformat(d["utc"]) for d in [freeze,exe,gate,opened]];assert ts==sorted(ts)
assert opened["sha256_liberacao_final"]==sha(O/"liberacao_final.json")
result={"metricas_teste_conferidas_com_sklearn":True,"F1_OOF_conferido_independentemente":True,"limites_IC_validos":True,"STL_copias_conferidos":count,"STL_alterados":0,"STL_gravados_na_etapa":0,"ordem_congelamentos_abertura_valida":True,"aprovado":True}
(O/"qa/auditoria_independente.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
