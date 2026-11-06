"""Auditoria local de proveniência, unidades, privacidade e congelamentos."""
from pathlib import Path
import csv,json,hashlib,sys,re
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa10"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={};issues=[]
for stage,key in [("etapa4","hashes"),("etapa5","hashes"),("etapa7b","files"),("etapa8","files"),("etapa9","source_files")]:
 d=json.loads((ROOT/stage/"congelamento.json").read_text());rows=[]
 for name,h in d[key].items():
  p=ROOT/name if name.startswith("etapa") else ROOT/stage/name
  ok=p.is_file() and sha(p)==h;rows.append({"arquivo":str(p.relative_to(ROOT)),"corresponde":ok,"sha256_esperado":h})
  if not ok:issues.append("hash congelado: "+str(p.relative_to(ROOT)))
 checks[stage]={"arquivos":len(rows),"intactos":all(r["corresponde"] for r in rows),"verificacoes":rows}
# Registro: todas as linhas e cópias existem e correspondem ao hash no momento da emissão.
claims=list(csv.DictReader((OUT/"registro_afirmacoes.csv").open()))
for c in claims:
 p=OUT/c["copia_auditavel"]
 if not p.exists() or sha(p)!=c["sha256_copia"]:issues.append("fonte: "+c["afirmacao_ID"]);continue
 if not 1<=int(c["linha"])<=len(p.read_text().splitlines()):issues.append("linha: "+c["afirmacao_ID"])
# Conteúdo compartilhado na divisão geométrica e CV.
pd0=pd.read_csv(OUT/"fontes/etapa4/resultados/por_paciente.csv")
dev=set(pd0[pd0.subset=="dev"].ID_conteudo);test=set(pd0[pd0.subset=="test"].ID_conteudo)
if dev&test:issues.append("conteudo compartilhado dev/test")
f=pd.read_csv(OUT/"fontes/etapa7b/conteudos_folds.csv");e=f[f.elegivel_3_grupos]
if e.groupby("ID_conteudo").fold.nunique().max()!=1:issues.append("alias em folds distintos")
# CDF e taxas >t são complementares para cada método nos quatro limiares.
b=json.loads((OUT/"fontes/etapa4/resultados/bootstrap_resumo.json").read_text());cdf=json.loads((OUT/"fontes/etapa4/resultados/CDF.json").read_text())
for subset in ["dev","test"]:
 for m in ["pca_controle","anatomica","multi5_rmse"]:
  d=cdf[subset][m]
  for t in [2,3,5,10]:
   i=d["x"].index(float(t));a=1-d["cdf_patient_content_mean"][i];z=b[subset][m]["content_cluster_bootstrap"][f"failure_rate_{t}deg"]["estimate"]
   if not np.isclose(a,z):issues.append(f"CDF/limiar {subset}/{m}/{t}")
# Procurar nomes de origem somente em memória; nunca imprimir nomes ou correspondências.
private=ROOT/"etapa5/privado/id_pasta_local.csv"
forbidden=[]
if private.exists():
 for row in csv.DictReader(private.open()):
  for k,v in row.items():
   if "pasta" in k.lower() and v:
    # Parte específica do diretório, excluindo rótulos genéricos de grupo.
    part=Path(v).name.strip()
    if len(part)>10:forbidden.append(part.casefold())
scanned=0;leaks=[]
for p in OUT.rglob("*"):
 if not p.is_file() or "qa" in p.relative_to(OUT).parts:continue
 if p.suffix.lower() in [".csv",".json",".md",".py",".sh",".txt",".html",".tex",".svg"]:
  s=p.read_text(errors="replace").casefold();scanned+=1
  if any(v in s for v in forbidden):leaks.append(str(p.relative_to(OUT)))
 if p.suffix.lower()==".stl":issues.append("STL incluído no pacote")
if leaks:issues.append("strings de origem em arquivos: "+",".join(leaks))
result={"fontes_congeladas":checks,"afirmacoes":len(claims),"linhas_e_hashes_validos":not any(x.startswith(("fonte:","linha:")) for x in issues),"dev_conteudos":len(dev),"teste_conteudos":len(test),"conteudos_compartilhados":len(dev&test),"aliases_mesmo_fold":e.groupby("ID_conteudo").fold.nunique().max()==1,"cdf_compativel_com_limiares":not any(x.startswith("CDF") for x in issues),"auditoria_strings":{"arquivos_examinados":scanned,"arquivos_com_strings_origem":leaks},"problemas":issues,"aprovado":not issues}
(OUT/"qa/auditoria.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda v:bool(v))+"\n")
print(json.dumps({"afirmacoes":len(claims),"dev_conteudos":len(dev),"teste_conteudos":len(test),"hashes_congelados_intactos":all(v["intactos"] for v in checks.values()),"problemas":issues,"aprovado":not issues},ensure_ascii=False))
raise SystemExit(bool(issues))
