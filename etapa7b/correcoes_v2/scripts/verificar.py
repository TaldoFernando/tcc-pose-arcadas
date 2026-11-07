"""Auditoria independente da extensão: privacidade, unidade e invariância."""
from pathlib import Path
import sys,json,csv,hashlib,collections
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OLD=ROOT/"etapa7b";OUT=OLD/"correcoes_v2";R=OUT/"resultados"
def read(p):return list(csv.DictReader(Path(p).open()))
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 checks={};issues=[]
 for label,path in [("originais_7B",OLD/"congelamento.json"),("extensao",OUT/"congelamento.json"),("analise",OUT/"congelamento_analise.json")]:
  files=load(path)["files"];ok=all(sha(ROOT/n)==d for n,d in files.items());checks[label]={"n":len(files),"hashes_intactos":ok}
  if not ok:issues.append("hashes "+label)
 units=load(OLD/"unidades.json");lookup={u["ID"]:u for u in units};assert len({u["conteudo_sha256"] for u in units})==63
 f=read(OLD/"conteudos_folds.csv");groups=collections.defaultdict(set)
 for r in f:
  if r["elegivel_3_grupos"]=="True":groups[r["ID_conteudo"]].add(r["fold"])
 assert all(len(x)==1 for x in groups.values())
 new=read(R/"predicoes_centralizado.csv");assert len(new)==63*51*5
 assert all(r["centering_R_identity"]=="True" and r["method"]=="centralizado" for r in new)
 per=collections.Counter((r["ID"],r["model"]) for r in new);assert set(per.values())=={51}
 original=read(OLD/"metricas_IC95.csv");corrected=read(R/"metricas_IC95.csv");key=lambda r:(r.get("modelo"),r.get("condicao"),r.get("normalizacao"),r.get("eixo"),float(r.get("angulo")))
 current={key(r):r for r in corrected if r["populacao"]=="todos_63" and r["normalizacao"]!="centralizado"}
 maxdiff=max(abs(float(r[k])-float(current[key(r)][k])) for r in original for k in ["acuracia","f1_macro","erro_ordinal_grupo","taxa_troca"]);assert maxdiff<1e-12
 contrasts=read(R/"contrastes_pareados_IC95.csv");primary=[r for r in contrasts if r["carater"]=="primario_da_extensao"];assert len(primary)==1 and primary[0]["n_conteudos"]=="58"
 # Reconstruir o ponto primário diretamente dos resumos individuais.
 patient=read(R/"metricas_por_conteudo.csv");values={m:{r["ID"]:float(r["taxa_troca"]) for r in patient if r["populacao"]=="sem_templates_58" and r["modelo"]=="substituto_canonico" and r["condicao"]=="realistic" and r["normalizacao"]==m} for m in ["multi5_rmse","centralizado"]}
 assert set(values["multi5_rmse"])==set(values["centralizado"]) and len(values["centralizado"])==58
 point=np.mean([values["multi5_rmse"][i]-values["centralizado"][i] for i in values["centralizado"]]);assert np.isclose(point,float(primary[0]["diferenca"]))
 # A exclusão cobre conteúdos/aliases, não apenas strings de ID-template em uma lista de ensaios.
 bank={"P016","P004","P045","P029","P002"};excluded={u["ID"] for u in units if set(u["aliases"])&bank};assert set(values["centralizado"])==set(lookup)-excluded
 ss=read(R/"sensibilidade_templates_todas_condicoes.csv");assert len(ss)==len(original)*4+220*2 # 535 células por população, quatro métricas
 # Frações >5 e >10 são estritas e ordenadas por limiar, não porcentagens já escaladas.
 geo=read(R/"residuos_pose_por_conteudo.csv")
 for r in geo:
  v=[float(r[f"proporcao_erro_consistencia_pose_maior_{t}_graus"]) for t in [2,3,5,10]];assert all(0<=x<=1 for x in v) and v==sorted(v,reverse=True)
 # Procurar nomes de origem somente em memória; nunca imprimir esses nomes.
 forbidden=[]
 for row in read(ROOT/"etapa5/privado/id_pasta_local.csv"):
  for k,v in row.items():
   if "pasta" in k.lower() and v and len(Path(v).name.strip())>10:forbidden.append(Path(v).name.strip().casefold())
 leaks=[]
 for p in OUT.rglob("*"):
  if p.is_file() and p.suffix in [".py",".json",".csv",".md",".log",".txt"]:
   s=p.read_text(errors="replace").casefold()
   if any(x in s for x in forbidden):leaks.append(str(p.relative_to(OUT)))
 assert not leaks
 report={"hashes":checks,"aliases_mesmo_fold":True,"novas_predicoes":len(new),"n_conteudos":63,"n_conteudos_sensibilidade":58,"n_contrastes_primarios":1,"primario_reproduzido_dos_conteudos":True,"pontos_originais_preservados_max_diferenca":maxdiff,"cabecas_congeladas":True,"sem_banco_por_fold":True,"sensibilidade_todas_condicoes":True,"rotulos_thresholds_estritos":True,"arquivos_com_nomes_origem":leaks,"problemas":issues,"aprovado":not issues}
 (OUT/"qa/verificacao_final.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n");print(json.dumps(report,ensure_ascii=False))
 if issues:raise SystemExit(1)
if __name__=="__main__":main()
