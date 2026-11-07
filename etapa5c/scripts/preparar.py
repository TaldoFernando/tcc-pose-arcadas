"""Auditoria sem desempenho, suspeitas geométricas e split congelado por grupos."""
import os
for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:os.environ[k]="1"
from pathlib import Path
import sys,json,csv,hashlib,datetime,collections
import numpy as np
from scipy.spatial import cKDTree
from sklearn.model_selection import StratifiedGroupKFold
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"etapa5c";SEED=20261122
sys.path[:0]=[str(ROOT/"etapa5"),str(ROOT/"etapa6")]
from anatomical_pair import anatomical_frame,run_icp
from rigid_icp import sample_surface
from render_views import read_stl
BANK={"P016","P004","P045","P029","P002"}
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
def write(n,rows):
 with (OUT/n).open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Union:
 def __init__(self,ids):self.d={i:i for i in ids}
 def find(self,i):
  while self.d[i]!=i:self.d[i]=self.d[self.d[i]];i=self.d[i]
  return i
 def join(self,a,b):
  a,b=self.find(a),self.find(b);self.d[max(a,b)]=min(a,b)

def main():
 if (OUT/"congelamento.json").exists():raise SystemExit("Divisao ja congelada; nao sobrescrever.")
 # Os rótulos só auditam conflitos e estratificam; nenhuma predição é carregada.
 pairs=load(ROOT/"etapa5/pares_ids.json");labels={r["ID"]:r for r in csv.DictReader((ROOT/"etapa5/rotulos_local.csv").open())};blocks=collections.defaultdict(list)
 for p in pairs:blocks[(p["superior"]["sha256"],p["inferior"]["sha256"])].append(p)
 contents=[];audit=[];excluded=[]
 for key,pp in sorted(blocks.items(),key=lambda kv:min(p["id"] for p in kv[1])):
  ids=sorted(p["id"] for p in pp);gs={labels[i]["grupo"] for i in ids};ss={labels[i]["goslon"] for i in ids};conflict=len(gs)>1 or len(ss)>1
  entry={"ID_conteudo":ids[0],"IDs":";".join(ids),"n_IDs":len(ids),"grupos":";".join(sorted(gs)),"GOSLON":";".join(sorted(ss)),"conflito_grupo":len(gs)>1,"conflito_GOSLON":len(ss)>1,"excluido":conflict};audit.append(entry)
  if conflict:excluded.append(entry);continue
  contents.append({"ID":ids[0],"aliases":ids,"grupo":int(next(iter(gs))),"goslon":int(next(iter(ss))),"conteudo_hash":hashlib.sha256("|".join(key).encode()).hexdigest(),"pair":next(p for p in pp if p["id"]==ids[0])})
 write("auditoria_rotulos.csv",audit);write("exclusoes_rotulos.csv",excluded)
 # Triagem de identidade proxy sem rótulos ou resultados de classificador.
 points={};descriptors={};areas={};frame={}
 for c in contents:
  i=c["ID"];p=c["pair"];clouds=[];dv=[];ar=[]
  for j,a in enumerate(["superior","inferior"]):
   tri=read_stl(ROOT/"etapa5"/p[a]["arquivo"]);x=sample_surface(tri,10000,SEED+17+j);clouds.append(x)
   ev=np.linalg.eigvalsh(np.cov(x,rowvar=False));dv.extend(np.sqrt(np.maximum(ev,1e-12)))
   ar.append(float(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1).sum()/2))
  points[i]=clouds;descriptors[i]=np.array(dv);areas[i]=np.array(ar);frame[i]=anatomical_frame(*clouds,1.,"pca_sign")[0]
  print("GEOMETRIA",i,flush=True)
 uf=Union([c["ID"] for c in contents]);candidate_rows=[];near=[];ids=sorted(points)
 for ai,i in enumerate(ids):
  for j in ids[ai+1:]:
   rel=float(np.max(abs(descriptors[i]-descriptors[j])/np.maximum((descriptors[i]+descriptors[j])/2,1e-12)));area=float(np.max(abs(areas[i]-areas[j])/np.maximum((areas[i]+areas[j])/2,1e-12)))
   if rel>.05 or area>.05:continue
   u,l=points[i];tu,tl=points[j];source=np.concatenate([u[::5],l[::5]]);target=np.concatenate([tu[::5],tl[::5]]);r0=frame[j]@frame[i].T;T=np.eye(4);T[:3,:3]=r0;T[:3,3]=target.mean(0)-r0@source.mean(0)
   fit=run_icp(source,target,T,max_iterations=40);R=np.array(fit["R"]);t=np.array(fit["t"]);ds=[];q95=[]
   for x,y in zip(points[i],points[j]):
    z=x@R.T+t;a=cKDTree(y).query(z)[0];b=cKDTree(z).query(y)[0];ds.append(float(np.sqrt((np.mean(a*a)+np.mean(b*b))/2)));q95.append(float(np.quantile(np.r_[a,b],.95)))
   flagged=max(ds)<=.5 and max(q95)<=1.;row={"ID_A":i,"ID_B":j,"RMS_PCA_desvio_rel_max":rel,"area_desvio_rel_max":area,"RMSE_superior_mm_assumido":ds[0],"RMSE_inferior_mm_assumido":ds[1],"P95_superior_mm_assumido":q95[0],"P95_inferior_mm_assumido":q95[1],"suspeita_revisao_manual":flagged,"identidade_confirmada":False};candidate_rows.append(row)
   if flagged:near.append(row);uf.join(i,j)
 # Sempre entregar uma tabela de suspeitas, mesmo vazia.
 cols=["ID_A","ID_B","RMS_PCA_desvio_rel_max","area_desvio_rel_max","RMSE_superior_mm_assumido","RMSE_inferior_mm_assumido","P95_superior_mm_assumido","P95_inferior_mm_assumido","suspeita_revisao_manual","identidade_confirmada"]
 for name,rows in [("geometria_candidatos.csv",candidate_rows),("suspeitas_mesmo_paciente.csv",near)]:
  with (OUT/name).open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
 for c in contents:c["bloco_paciente_proxy"]=uf.find(c["ID"]);c.pop("pair")
 save("conteudos_elegiveis.json",contents)
 n=len(contents);target_n=int(np.floor(.25*n+.5));counts=np.array([sum(c["grupo"]==g for c in contents) for g in [1,2,3]]);ideal=target_n*counts/n;quota=np.floor(ideal).astype(int)
 for ix in np.argsort(-(ideal-quota),kind="stable")[:target_n-int(quota.sum())]:quota[ix]+=1
 byblock=collections.defaultdict(list)
 for c in contents:byblock[c["bloco_paciente_proxy"]].append(c)
 forced={b for b,cs in byblock.items() if any(set(c["aliases"])&BANK for c in cs)};available=sorted(set(byblock)-forced);rng=np.random.default_rng(SEED);rng.shuffle(available)
 # Programação dinâmica: ordem aleatória congelada, sem avaliar qualquer modelo.
 dp={(0,0,0):[]}
 for b in available:
  k=tuple(sum(c["grupo"]==g for c in byblock[b]) for g in [1,2,3])
  for s,selected in list(dp.items()):
   new=tuple(s[j]+k[j] for j in range(3))
   if all(new[j]<=quota[j] for j in range(3)) and new not in dp:dp[new]=selected+[b]
 goal=tuple(quota)
 if goal not in dp:goal=min(dp,key=lambda s:(sum((s[j]-int(quota[j]))**2 for j in range(3)),abs(sum(s)-target_n)))
 testblocks=set(dp[goal]);dev=[c for c in contents if c["bloco_paciente_proxy"] not in testblocks];test=[c for c in contents if c["bloco_paciente_proxy"] in testblocks]
 assert not {c["bloco_paciente_proxy"] for c in dev}&testblocks
 split={"seed":SEED,"unidade":"bloco-paciente proxy, identidade clinica nao confirmada","rotulos_usados_antes_hash":"somente conflitos e estratificacao, nenhuma metrica de classificador","dev_IDs":[c["ID"] for c in dev],"test_IDs":[c["ID"] for c in test],"quota_alvo_por_grupo":dict(zip(["1","2","3"],map(int,quota))),"banco_forcado_apenas_dev":sorted(BANK),"blocos_dev_forcados":sorted(forced),"teste_inedito":False,"exposicao_historica":True};save("divisao.json",split)
 cv=[]
 for rep,seed in enumerate([20261123,20261124,20261125,20261126,20261127]):
  sg=StratifiedGroupKFold(4,shuffle=True,random_state=seed);y=[c["grupo"] for c in dev];g=[c["bloco_paciente_proxy"] for c in dev]
  for fold,(tr,va) in enumerate(sg.split(dev,y,g)):
   train=[dev[k]["ID"] for k in tr];val=[dev[k]["ID"] for k in va]
   assert not {dev[k]["bloco_paciente_proxy"] for k in tr}&{dev[k]["bloco_paciente_proxy"] for k in va}
   cv.append({"repeticao":rep,"seed":seed,"fold":fold,"train_IDs":train,"val_IDs":val,"test_IDs":[]})
 save("folds_CV.json",cv)
 sizes=[]
 def size(name,cs,rep=-1,fold=-1):
  for group in ["todos",1,2,3]:
   cc=[c for c in cs if group=="todos" or c["grupo"]==group];sizes.append({"conjunto":name,"repeticao":rep,"fold":fold,"grupo":group,"n_conteudos":len(cc),"n_blocos_paciente_proxy":len({c["bloco_paciente_proxy"] for c in cc}),"n_IDs_fisicos":sum(len(c["aliases"]) for c in cc),"menos_5_blocos_no_teste":name=="teste" and group!="todos" and len({c["bloco_paciente_proxy"] for c in cc})<5})
 size("elegiveis",contents);size("desenvolvimento",dev);size("teste",test)
 lookup={c["ID"]:c for c in contents}
 for f in cv:size("CV_treino",[lookup[i] for i in f["train_IDs"]],f["repeticao"],f["fold"]);size("CV_validacao",[lookup[i] for i in f["val_IDs"]],f["repeticao"],f["fold"])
 write("tamanhos.csv",sizes)
 source=[ROOT/"etapa5/pares_ids.json",ROOT/"etapa5/rotulos_local.csv",OUT/"plano_previo.json",OUT/"divisao.json",OUT/"folds_CV.json",OUT/"conteudos_elegiveis.json",OUT/"scripts/preparar.py",ROOT/"etapa7b/camera_config_proprio.json",ROOT/"etapa7b/protocolo.json",ROOT/"etapa6/stl/modelo_normalizacao.npz"]
 save("congelamento.json",{"utc":now(),"before_classifier_analysis_with_labels":True,"labels_used_only_for_conflicts_and_stratification":True,"test_locked":True,"files":{str(p.relative_to(ROOT)):sha(p) for p in source},"sha256_divisao":sha(OUT/"divisao.json"),"geometria_suspeitas":len(near),"geometria_candidatos":len(candidate_rows)})
 (OUT/"divisao.sha256").write_text(sha(OUT/"divisao.json")+"  divisao.json\n")
 save("status.json",{"status":"DIVISAO_CONGELADA_TESTE_BLOQUEADO","n_elegiveis":n,"n_dev":len(dev),"n_teste":len(test),"n_suspeitas_proximidade":len(near),"rotulos_conflitantes_excluidos":len(excluded),"patient_id_confirmado":False})
 print(json.dumps({"conteudos":n,"dev":len(dev),"teste":len(test),"quotas":split["quota_alvo_por_grupo"],"suspeitas":len(near),"sha256_divisao":sha(OUT/"divisao.json")}),flush=True)
if __name__=="__main__":main()
