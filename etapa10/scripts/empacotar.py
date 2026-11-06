from pathlib import Path
import json,csv,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa10"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Hashes de código e artefatos necessários à reprodução científica completa.
files=[]
for stage in ["etapa1","etapa2","etapa3","etapa4","etapa5","etapa6","etapa7","etapa7b","etapa8","etapa9"]:
 for p in (ROOT/stage).rglob("*.py"):
  rel=p.relative_to(ROOT)
  if any(x in rel.parts for x in [".venv","__pycache__","privado","copias","dados","static"]):continue
  files.append({"arquivo":str(rel),"sha256":sha(p),"tipo":"codigo"})
for folder in ["etapa7b/backbone","etapa7b/checkpoints","etapa7b/features"]:
 for p in (ROOT/folder).rglob("*"):
  if p.is_file():files.append({"arquivo":str(p.relative_to(ROOT)),"sha256":sha(p),"tipo":"peso_ou_feature_nao_incluido"})
for s in ["etapa6/stl/modelo_normalizacao.npz","etapa6/stl/transformacoes.json","etapa7b/predicoes_oof.csv","etapa7b/congelamento.json","etapa4/congelamento.json","etapa5/congelamento.json","etapa8/congelamento.json","etapa9/congelamento.json"]:
 p=ROOT/s;files.append({"arquivo":s,"sha256":sha(p),"tipo":"entrada_congelada_ou_predicoes"})
(OUT/"reproducao/arquivos_experimento.json").write_text(json.dumps(files,ensure_ascii=False,indent=2)+"\n")
pairs=json.loads((ROOT/"etapa5/pares_ids.json").read_text());rows=[]
for p in pairs:
 for role in ["superior","inferior"]:rows.append({"ID":p["id"],"arcada":role,"sha256":p[role]["sha256"]})
with (OUT/"reproducao/hashes_dados_pareados.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["ID","arcada","sha256"]);w.writeheader();w.writerows(rows)
# QA de layout é local e excluída da distribuição.
paths=[]
for p in sorted(OUT.rglob("*")):
 if not p.is_file():continue
 rel=p.relative_to(OUT)
 if any(x in rel.parts for x in ["qa","__pycache__"]):continue
 if p.suffix in [".zip",".pyc"] or str(rel) in ["reproducao/manifesto_pacote.json","reproducao/pacote_sha256.txt"]:continue
 paths.append(p)
manifest={"escopo":"Artefatos e fontes sanitizadas da Etapa 10; exclui QA, STL, pesos, nomes de origem e tabela privada","arquivos":[{"arquivo":str(p.relative_to(OUT)),"bytes":p.stat().st_size,"sha256":sha(p)} for p in paths]}
mp=OUT/"reproducao/manifesto_pacote.json";mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
archive=OUT/"pacote_reproducao.zip"
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in paths+[mp]:z.write(p,Path("etapa10")/p.relative_to(OUT))
(OUT/"reproducao/pacote_sha256.txt").write_text(sha(archive)+"  pacote_reproducao.zip\n")
print(json.dumps({"arquivos":len(paths)+1,"zip_MB":round(archive.stat().st_size/1024**2,2),"arcadas_com_hash":len(rows)},ensure_ascii=False))
