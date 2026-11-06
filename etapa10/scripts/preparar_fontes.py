"""Exporta somente fontes permitidas, sem nomes de origem nem malhas."""
from pathlib import Path
import csv,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"etapa10"
JSONS=["etapa3/resultados/resumo.json",
"etapa4/resultados/bootstrap_resumo.json","etapa4/resultados/bootstrap_contrastes.json","etapa4/resultados/CDF.json","etapa4/resultados/oraculos292_resumo.json","etapa4/divisao.json","etapa4/congelamento.json","etapa4/escolhas.json",
"etapa5/resultados/estratos_bootstrap.json","etapa5/resultados/correlacoes.json","etapa5/resultados/balanceado_bootstrap.json","etapa5/protocolo.json",
"etapa7b/protocolo.json","etapa7b/status.json","etapa7b/congelamento.json","etapa7b/camera_config_proprio.json","etapa7b/residuos_pose.json","etapa7b/treinamento.json",
"etapa7/status.json","etapa8/status.json","etapa9/status.json"]
CSVS=["etapa5/resultados/por_conteudo_grupo.csv","etapa5/resultados/mediana_das_medianas_grupo.csv","etapa5/resultados/repeticoes_resumo.csv",
"etapa7b/metricas_IC95.csv","etapa7b/metricas_por_grupo_IC95.csv","etapa7b/diferencas_pareadas_IC95.csv","etapa7b/limiares_tolerancia.csv","etapa7b/conteudos_folds.csv","etapa4/resultados/componentes_rotacao.csv"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writecsv(p,rows,fields):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
manifest=[]
for s in JSONS+CSVS:
 p=ROOT/s;dst=OUT/"fontes"/s;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
 manifest.append({"origem":s,"copia":str(dst.relative_to(OUT)),"sha256_origem":sha(p),"sha256_copia":sha(dst),"transformacao":"copia integral permitida"})
p=ROOT/"etapa4/resultados/por_paciente.csv"
rows=list(csv.DictReader(p.open()));content={}
for r in rows:content.setdefault(r["content_group"],[]).append(r["id"])
content={k:min(v) for k,v in content.items()}
fields=[c for c in rows[0] if c not in ["paciente","content_group"]]+["ID_conteudo"]
safe=[{**{k:r[k] for k in fields if k!="ID_conteudo"},"ID_conteudo":content[r["content_group"]]} for r in rows]
dst=OUT/"fontes/etapa4/resultados/por_paciente.csv";writecsv(dst,safe,fields)
manifest.append({"origem":str(p.relative_to(ROOT)),"copia":str(dst.relative_to(OUT)),"sha256_origem":sha(p),"sha256_copia":sha(dst),"transformacao":"coluna de pasta removida; hash de conteudo substituido pelo menor ID; mesma ordem de linhas"})
# Inventário agregado sem nomes de arquivo/pasta.
c=json.loads((ROOT/"config.json").read_text())
safe={k:c[k] for k in ["stl","stl_unicos_sha256","pastas_paciente_com_stl","arcadas","watertight","unidade"]}
# Não copiar objetos que possam conter exemplos identificáveis: resumir apenas contagens escalares.
safe={k:v for k,v in safe.items() if isinstance(v,(int,float,str,bool))}
(OUT/"fontes/inventario_resumo.json").write_text(json.dumps(safe,ensure_ascii=False,indent=2)+"\n")
manifest.append({"origem":"config.json","copia":"fontes/inventario_resumo.json","sha256_origem":sha(ROOT/"config.json"),"sha256_copia":sha(OUT/"fontes/inventario_resumo.json"),"transformacao":"somente contagens escalares; sem nomes"})
(OUT/"reproducao/fontes_manifesto.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
print("Fontes anonimizadas:",len(manifest))
