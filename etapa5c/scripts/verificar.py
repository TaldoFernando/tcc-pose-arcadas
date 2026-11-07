"""Auditoria de divisão, OOF, bloqueio final e privacidade, sem escolher modelos."""
from pathlib import Path
import json,csv,hashlib,collections,argparse
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa5c"
def load(p):return json.loads(Path(p).read_text())
def read(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(final=False):
 checks={}
 for name in ["congelamento.json","congelamento_execucao.json"]:
  files=load(OUT/name)["files"];assert all(sha(ROOT/n)==h for n,h in files.items());checks[name]=len(files)
 s=load(OUT/"divisao.json");dev=load(OUT/"desenvolvimento.json");lookup={c["ID"]:c for c in dev};testset=set(s["test_IDs"]);devset=set(s["dev_IDs"]);assert not testset&devset
 allc=load(OUT/"conteudos_elegiveis.json");alook={c["ID"]:c for c in allc}
 assert len({alook[i]["conteudo_hash"] for i in devset}|{alook[i]["conteudo_hash"] for i in testset})==len(allc)
 assert not {alook[i]["bloco_paciente_proxy"] for i in devset}&{alook[i]["bloco_paciente_proxy"] for i in testset}
 bank={"P016","P004","P045","P029","P002"};assert bank<=devset and not bank&testset
 excluded=read(OUT/"exclusoes_rotulos.csv");assert len(excluded)==2
 assert not {x for e in excluded for x in e["IDs"].split(";")}&set(i for c in allc for i in c["aliases"])
 folds=load(OUT/"folds_CV.json");assert len(folds)==20
 logs=load(OUT/"resultados/treinamento_CV.json")
 for l in logs:
  assert set(l["train_IDs"])|set(l["val_IDs"])==devset and not set(l["train_IDs"])&set(l["val_IDs"]);assert not (set(l["train_IDs"])|set(l["val_IDs"]))&testset
 rows=read(OUT/"resultados/predicoes_OOF.csv");assert len(rows)==len(dev)*252*3*5
 by=collections.defaultdict(set)
 for r in rows:
  assert r["ID"] in devset and r["ID"] not in testset;by[(r["ID"],r["repeticao"])].add(r["fold"])
 assert len(by)==len(dev)*5 and all(len(v)==1 for v in by.values())
 key=lambda r:(r["ID"],r["repeticao"],r["modelo"],r["condicao"],r["normalizacao"],r["eixo"],r["angulo"],r["sinal"],r["ensaio"])
 assert len({key(r) for r in rows})==len(rows)
 rr=read(OUT/"resultados/metricas_OOF_IC95.csv");assert {r["n_blocos_paciente_proxy"] for r in rr if r["populacao"]=="desenvolvimento_completo"}=={str(len(dev))}
 assert {r["n_blocos_paciente_proxy"] for r in rr if r["populacao"]=="sensibilidade_sem_banco"}=={str(len(dev)-5)}
 assert sha(OUT/"divisao.json")==load(OUT/"congelamento.json")["sha256_divisao"]
 result={"hashes_verificados":checks,"test_n":len(testset),"dev_n":len(devset),"conteudos_compartilhados":0,"blocos_proxy_compartilhados":0,"templates_todos_no_dev":True,"n_ajustes_CV":len(logs),"OOF_predicoes":len(rows),"OOF_IDs_exatamente_dev":True,"OOF_uma_validacao_por_repeticao":True,"teste_avaliado":final,"sem_id_clinico_confirmado":True,"identidade_geometrica_nao_prova_paciente":True}
 if not final:assert not (OUT/"teste_bloqueado/abertura.json").exists()
 else:
  gate=load(OUT/"liberacao_final.json");assert all(sha(ROOT/n)==h for n,h in gate["files"].items())
  pred=read(OUT/"resultados/predicoes_teste_final.csv");assert len(pred)==len(testset)*3 and {r["ID"] for r in pred}==testset
  assert {r["condicao"] for r in pred}=={"canonical"};assert not list((OUT/"resultados").glob("*tolerancia*teste*"))
  assert not testset&set(gate["train_only_development_IDs"])
  status=load(OUT/"resultados/status_teste_final.json");assert status["ajustes_apos_teste"] is False
  result["teste_somente_canonico"]=True;result["teste_sem_tuning"]=True
 # Hash de arcada única compartilhado por conteúdos distintos: risco além do par.
 pairs={p["id"]:p for p in load(ROOT/"etapa5/pares_ids.json")};h=collections.defaultdict(set)
 for c in allc:
  for a in ["superior","inferior"]:h[(a,pairs[c["ID"]][a]["sha256"])].add(c["ID"])
 assert not any(len(ids)>1 for ids in h.values());result["arcadas_identicas_em_conteudos_distintos"]=0
 # Nenhuma string de pasta de origem nos relatórios/código da etapa.
 forbidden=[]
 for r in read(ROOT/"etapa5/privado/id_pasta_local.csv"):
  for k,v in r.items():
   if "pasta" in k.lower() and v and len(Path(v).name.strip())>10:forbidden.append(Path(v).name.strip().casefold())
 leaks=[]
 for p in OUT.rglob("*"):
  if p.is_file() and p.suffix in [".json",".csv",".py",".md",".txt",".log"]:
   if any(x in p.read_text(errors="replace").casefold() for x in forbidden):leaks.append(str(p.relative_to(OUT)))
 assert not leaks;result["strings_origem_encontradas"]=leaks;result["aprovado"]=True
 name="verificacao_final.json" if final else "verificacao_pre_teste.json";(OUT/"qa"/name).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n");print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--final",action="store_true");a=p.parse_args();verify(a.final)
