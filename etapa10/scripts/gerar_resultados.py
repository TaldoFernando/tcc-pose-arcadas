"""Reconstrói tabelas, figuras e registro de afirmações a partir das fontes locais."""
from pathlib import Path
import csv,json,re,hashlib,html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
ROOT=Path(__file__).resolve().parents[1]; F=ROOT/"fontes"
SEED=20261130; B=10000
METHODS=["pca_controle","anatomica","point_plane","multi5_rmse"]
MAIN=["pca_controle","anatomica","multi5_rmse"]
LABEL={"pca_controle":"Controle PCA","controle":"Controle PCA","anatomica":"Regra orientada","point_plane":"Ponto a plano","multi5_rmse":"Multi5 RMSE","nenhuma":"Sem normalização","substituto_canonico":"Substituto canônico","substituto_aug10":"Substituto aug 10°","substituto_aug20":"Substituto aug 20°","logistica_descritores":"Logística","majoritaria":"Majoritária"}
COLORS={"pca_controle":"#222222","anatomica":"#777777","multi5_rmse":"#007c83"}
claims=[]; tables=[]; figures=[]
GEOM="Consistência em relação à normalização não perturbada do próprio método; não é correção anatômica. IC exploratório por conteúdo, sem ajuste por multiplicidade."
CLF="MODELO SUBSTITUTO, não Goslon AI. Rótulos de pasta não auditados; banco geométrico global pode conter conteúdos dos folds de teste. IC de predições OOF fixas, sem retreino."
def load(s):return json.loads((F/s).read_text())
def csvrows(s):return list(csv.DictReader((F/s).open()))
def num(x,n=2):
 v=float(x);v=0.0 if abs(v)<0.5*10**(-n) else v
 return f"{v:.{n}f}".replace(".",",")
def interval(d,scale=1,n=2):return f'{num(d["estimate"]*scale,n)} [{num(d["CI95"][0]*scale,n)}; {num(d["CI95"][1]*scale,n)}]'
def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def json_location(p,keys):
 # Analisa tokens com posições; nenhum grep ambíguo entre chaves repetidas.
 text=p.read_text(); tokens=list(re.finditer(r'"(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\]:,]',text));i=0;loc={}
 def walk(path):
  nonlocal i
  loc[tuple(path)]=text.count("\n",0,tokens[i].start())+1
  t=tokens[i].group();i+=1
  if t=="{":
   while tokens[i].group()!="}":
    k=json.loads(tokens[i].group());i+=2;walk(path+[k])
    if tokens[i].group()==",":i+=1
   i+=1
  elif t=="[":
   j=0
   while tokens[i].group()!="]":
    walk(path+[str(j)]);j+=1
    if tokens[i].group()==",":i+=1
   i+=1
 walk([]);return loc[tuple(map(str,keys))]
def claim(text,source,unit,caveat,destination,keys=None,line=None,value=None):
 p=F/source if (F/source).exists() else ROOT/source
 n=line or json_location(p,keys or [])
 c={"afirmacao_ID":f"A{len(claims)+1:04d}","afirmacao":text,"valor":str(value) if value is not None else text,"arquivo_origem":source if (F/source).exists() else "etapa10/"+source,"linha":n,"localizador":"/"+"/".join(map(str,keys)) if keys else f"linha {n}","copia_auditavel":str(p.relative_to(ROOT)),"sha256_copia":hashfile(p),"unidade_analise":unit,"ressalva_obrigatoria":caveat,"destino":destination}
 claims.append(c);return c["afirmacao_ID"]
def writecsv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def tex(s):
 for a,b in [("\\","\\textbackslash{}"),("&","\\&"),("%","\\%"),("_","\\_"),("#","\\#")]:s=str(s).replace(a,b)
 return s

def table(slug,title,columns,rows,note):
 no=len(tables)+1;fname=f"{no:02d}_{slug}";items=[dict(zip(columns,row)) for row in rows]
 writecsv(ROOT/"tabelas"/(fname+".csv"),items)
 md=f"Tabela {no} – {title}\n\n"+"| "+" | ".join(columns)+" |\n"+"| "+" | ".join(["---"]*len(columns))+" |\n"
 md+="\n".join("| "+" | ".join(map(str,row))+" |" for row in rows)
 md+="\n\nFonte: elaboração própria, com base nos arquivos registrados em registro_afirmacoes.csv.\n\nNota: "+note+"\n"
 (ROOT/"tabelas"/(fname+".md")).write_text(md)
 lt="\\begin{table}[htbp]\n\\centering\n\\caption{"+tex(title)+"}\n\\label{tab:"+slug+"}\n\\small\n\\begin{tabular}{"+("l"*len(columns))+"}\n\\toprule\n"
 lt+=" & ".join(map(tex,columns))+" \\\\\n\\midrule\n"
 lt+="\n".join(" & ".join(map(tex,row))+" \\\\" for row in rows)
 lt+="\n\\bottomrule\n\\end{tabular}\n\n\\parbox{\\linewidth}{\\footnotesize Fonte: elaboração própria. Nota: "+tex(note)+"}\n\\end{table}\n"
 (ROOT/"tabelas"/(fname+".tex")).write_text(lt)
 tables.append({"numero":no,"titulo":title,"arquivo":fname,"colunas":columns,"linhas":rows,"nota":note})
 return "tabelas/"+fname+".csv"

s="etapa4/resultados/bootstrap_resumo.json";boot=load(s)
for subset in ["dev","test"]:
 rows=[]
 for m in METHODS:
  d=boot[subset][m]["content_cluster_bootstrap"];row=[LABEL[m],str(d["n"]),interval(d["mean_patient_median"])]
  for k in [2,3,5,10]:row.append(interval(d[f"failure_rate_{k}deg"],100))
  rows.append(row)
  for key in ["mean_patient_median"]+[f"failure_rate_{k}deg" for k in [2,3,5,10]]:
   q=d[key];claim(f"{subset}; {LABEL[m]}; {key}: {interval(q,100 if key.startswith('failure') else 1)}",s,"conteúdo-paciente; 17 dev ou 47 teste; ensaios repetidos",GEOM,"Tabela "+str(len(tables)+1),[subset,m,"content_cluster_bootstrap",key],value=json.dumps(q))
 table("geometria_"+subset,"Consistência geométrica no "+("desenvolvimento" if subset=="dev" else "teste interno"),["Método","n","Média medianas °",">2° %",">3° %",">5° %",">10° %"],rows,"Colunas >k° % indicam porcentagem com erro estritamente maior que k graus. IC95% percentil; 10.000 reamostragens de conteúdos, seed 20261107. n não é número de ensaios. Referência própria de cada método; não anatomia. Trim e posterior descartados, sem novos cálculos.")
s="etapa4/resultados/bootstrap_contrastes.json";contr=load(s);rows=[]
for subset in ["dev","test"]:
 for m in METHODS[1:]:
  d=contr[subset][m];rows.append([subset,LABEL[m],interval(d["delta_mean_patient_median"]),interval(d["delta_failure_rate5"],100)])
  for key in ["delta_mean_patient_median","delta_failure_rate5"]:
   claim(f"{subset}; {LABEL[m]} menos controle: {key} {interval(d[key],100 if 'failure' in key else 1)}",s,"contraste pareado por conteúdo-paciente",GEOM+" IC que inclui zero não demonstra diferença pelo protocolo.","Tabela 3",[subset,m,key])
table("contrastes","Contrastes pareados em relação ao controle PCA",["Conjunto","Variante","Δ média medianas °","Δ falha >5° p.p."],rows,"Variante menos controle; negativo indica menor valor. Mesmos conteúdos reamostrados entre métodos; IC95% pareados. Um IC que inclui zero não demonstra vantagem.")

s="etapa5/resultados/estratos_bootstrap.json";groups=load(s);rows=[]
for m in ["controle","anatomica","multi5_rmse"]:
 for g in ["1","2","3"]:
  d=groups[m][g];rows.append([LABEL[m],g,str(d["median_error_deg"]["n_patient_contents"]),interval(d["median_error_deg"]),interval(d["failure5"],100),interval(d["failure10"],100)])
  for key in ["median_error_deg","failure2","failure3","failure5","failure10","median_RMSE"]:
   claim(f"Grupo {g}; {LABEL[m]}; {key}: {interval(d[key],100 if key.startswith('failure') else 1)}",s,"conteúdo-paciente dentro do grupo no teste; n=21/10/16",GEOM+" Grupo/GOSLON extraídos de nomes; correspondência não validada.","Tabela 4 e suplemento estratos",[m,g,key])
table("grupos","Consistência estratificada por grupo no teste interno",["Método","Grupo","n","Média medianas °","Falha >5° %","Falha >10° %"],rows,"IC95% por conteúdo dentro do grupo, 10.000 reamostragens, seed 20261120. Grupo 1: 21 conteúdos; grupo 2: 10; grupo 3: 16. Rótulos não auditados; grupos não são cinco classes GOSLON.")
# Mediana entre as medianas, separada da média das medianas.
s="etapa5/resultados/mediana_das_medianas_grupo.csv";rows=[]
for i,r in enumerate(csvrows(s),2):
 rows.append([LABEL[r["method"]],r["grupo"],r["n_patient_contents"],f'{num(r["median_of_patient_medians_deg"])} [{num(r["CI95_low"])}; {num(r["CI95_high"])}]'])
 claim(f'Grupo {r["grupo"]}; {LABEL[r["method"]]}; mediana das medianas {rows[-1][-1]}°',s,"conteúdo-paciente dentro do grupo",GEOM+" Não confundir esta mediana com a média das medianas da Tabela 4.","Tabela 5",line=i)
table("medianas_grupos","Mediana entre conteúdos das medianas individuais",["Método","Grupo","n","Mediana das medianas °"],rows,"IC95% por conteúdo. Esta estatística difere da média das medianas individuais usada como estimando principal.")
# IC adicionais para componentes, derivados somente de resultados congelados.
patient=pd.read_csv(F/"etapa4/resultados/por_paciente.csv");comps=pd.read_csv(F/"etapa4/resultados/componentes_rotacao.csv")
mp=patient.drop_duplicates("id").set_index("id")["ID_conteudo"].to_dict()
rng=np.random.default_rng(SEED);axisrows=[]
for subset in ["dev","test"]:
 for m in MAIN:
  x=comps[(comps.subset==subset)&(comps.method==m)].copy()
  norm=np.sqrt((x[["lateral_deg","AP_deg","vertical_deg"]]**2).sum(axis=1))
  assert np.allclose(norm,x.error_deg,rtol=1e-6,atol=1e-6)
  measures=[]
  for axis in ["lateral","AP","vertical"]:
   a=x.groupby("id")[axis+"_deg"].apply(lambda y:np.median(np.abs(y)))
   a.index=a.index.map(mp);a=a.groupby(level=0).mean();measures.append(a)
  vals=np.array([a.values for a in measures]).T;idx=rng.integers(0,len(vals),size=(B,len(vals)));samples=vals[idx].mean(axis=1);lo,hi=np.quantile(samples,[.025,.975],axis=0)
  for j,axis in enumerate(["lateral","AP","vertical"]):axisrows.append({"conjunto":subset,"metodo":m,"eixo":axis,"conteudos":len(vals),"media_medianas_abs_graus":vals[:,j].mean(),"IC95_inf":lo[j],"IC95_sup":hi[j],"seed":SEED,"bootstrap":B})
writecsv(ROOT/"tabelas/eixos_derivados.csv",axisrows)
rows=[]
for subset in ["dev","test"]:
 for m in MAIN:
  z=[r for r in axisrows if r["conjunto"]==subset and r["metodo"]==m]
  rows.append([subset,LABEL[m],str(z[0]["conteudos"])]+[f'{num(r["media_medianas_abs_graus"])} [{num(r["IC95_inf"])}; {num(r["IC95_sup"])}]' for r in z])
for i,r in enumerate(axisrows,2):claim(f'{r["conjunto"]}; {LABEL[r["metodo"]]}; eixo {r["eixo"]}: média das medianas absolutas {num(r["media_medianas_abs_graus"])}°', "tabelas/eixos_derivados.csv","conteúdo-paciente; aliases agregados",GEOM+" Eixos geométricos do log SO(3), não Euler nem anatomia validada.","Tabela 6 e Figura 2",line=i,value=json.dumps(r))
table("eixos","Componentes do vetor de erro de rotação",["Conjunto","Método","n","Látero lateral °","AP °","Vertical °"],rows,"Média das medianas absolutas por ID e depois por conteúdo. IC95% adicionais calculados na Etapa 10, B=10.000, seed 20261130; nenhuma regra ou teste reajustado. Fonte primária: componentes_rotacao.csv e mapa sanitizado por_paciente.csv. Log SO(3) no frame geométrico P016; não ângulos de Euler.")
# Classificador substituto: métricas com todos os IC arquivados.
s="etapa7b/metricas_IC95.csv";metrics=csvrows(s)
def cirow(r,key,scale=1):return f'{num(float(r[key])*scale,3 if key in ["f1_macro","erro_ordinal_grupo"] else 2)} [{num(float(r[key+"_IC95_inf"])*scale,3 if key in ["f1_macro","erro_ordinal_grupo"] else 2)}; {num(float(r[key+"_IC95_sup"])*scale,3 if key in ["f1_macro","erro_ordinal_grupo"] else 2)}]'
for cond in ["canonical","realistic"]:
 rows=[]
 for i,r in enumerate(metrics,2):
  if r["condicao"]!=cond:continue
  if cond=="realistic" and r["modelo"]!="substituto_canonico":continue
  rows.append([LABEL[r["modelo"]] if cond=="canonical" else LABEL[r["normalizacao"]],cirow(r,"acuracia",100),cirow(r,"f1_macro"),cirow(r,"erro_ordinal_grupo"),cirow(r,"taxa_troca",100)])
  for key in ["acuracia","f1_macro","erro_ordinal_grupo","taxa_troca"]:
   claim(f'MODELO SUBSTITUTO; {r["modelo"]}; {cond}; {r["normalizacao"]}; {key}: {cirow(r,key,100 if key in ["acuracia","taxa_troca"] else 1)}',s,"63 conteúdos-paciente; predições out of fold; 20 repetições realistas por conteúdo" if cond=="realistic" else "63 conteúdos-paciente; uma predição out of fold por conteúdo",CLF+(" Ruído/recorte só nas nuvens de registro; contraste sem normalização inclui perda de enquadramento." if cond=="realistic" else ""),"Tabela "+str(len(tables)+1),line=i)
 table("substituto_"+cond,"Modelo substituto na condição "+("canônica" if cond=="canonical" else "realista"),["Modelo" if cond=="canonical" else "Normalização","Acurácia %","F1 macro","Erro ordinal grupo","Troca %"],rows,"MODELO SUBSTITUTO; não Goslon AI. IC95% de 10.000 bootstraps de conteúdos, seed 20351106, sem retreino. F1 é recalculado no conjunto, não por paciente. Erro ordinal usa grupos 1–3, não GOSLON 1–5. "+("Referência da troca é a predição canônica do próprio modelo; cenário sem normalização inclui translação livre e vistas vazias." if cond=="realistic" else "Normalização canônica multi5 global; independência da cadeia completa não assegurada."))
# Suplemento de todas as rotações e todos os limiares com IC, rastreável por linha.
sel=[]
for i,r in enumerate(metrics,2):
 if r["condicao"]!="rotation" or r["modelo"] not in ["substituto_canonico","substituto_aug10","substituto_aug20"]:continue
 sel.append(r)
 claim(f'MODELO SUBSTITUTO; {r["modelo"]}; rotação {r["angulo"]}°; {r["eixo"]}; {r["normalizacao"]}; troca {cirow(r,"taxa_troca",100)}%',s,"63 conteúdos-paciente, sinais ± mantidos juntos",CLF+" Na rotação pura, troca de normalizador altera a referência; resíduo quase zero mede equivariância, não robustez realista.","Figura 4 e suplemento tolerancia",line=i)
writecsv(ROOT/"tabelas/suplemento_tolerancia_IC95.csv",sel)
writecsv(ROOT/"tabelas/suplemento_classificacao_todas_metricas_IC95.csv",metrics)
rows=[]
s="etapa7b/limiares_tolerancia.csv"
for i,r in enumerate(csvrows(s),2):
 if r["modelo"] not in ["substituto_canonico","substituto_aug10","substituto_aug20"] or r["normalizacao"]!="nenhuma":continue
 rows.append([LABEL[r["modelo"]],r["eixo"],r["primeiro_angulo_troca_maior_5"],r["primeiro_angulo_troca_maior_10"]])
 claim(f'MODELO SUBSTITUTO; {r["modelo"]}; {r["eixo"]}; primeiro ângulo testado para troca >5%: {rows[-1][2]}°; >10%: {rows[-1][3]}°',s,"conteúdo-paciente; limiar descritivo entre ângulos testados",CLF+" Sem interpolação, IC de limiar ou garantia abaixo de 2°. Não é limiar clínico.","Tabela 9",line=i)
table("limiares_substituto","Primeiro ângulo testado acima das taxas de troca",["Modelo substituto","Eixo","Troca >5% °","Troca >10% °"],rows,"Sem normalização; ângulos testados 2, 3, 5, 10 e 20°, além de 0° de referência. Cruzamento pode ocorrer abaixo de 2°; não há limiar contínuo estimado nem IC para esse cruzamento.")
# Correlações exploratórias.
s="etapa5/resultados/correlacoes.json";corr=load(s);rows=[]
for m in ["controle","anatomica","multi5_rmse"]:
 for key,label in [("goslon_failure5","GOSLON × falha"),("RMSE_failure5","RMSE × falha")]:
  d=corr[m][key];rows.append([LABEL[m],label,str(d["n"]),f'{num(d["rho"],3)} [{num(d["CI95"][0],3)}; {num(d["CI95"][1],3)}]',num(d["permutation_p_two_sided"],4)])
  claim(f'{LABEL[m]}; {label}; rho {rows[-1][-2]}, p {rows[-1][-1]}',s,"conteúdo-paciente; 46 para GOSLON, 47 para RMSE",GEOM+" Associação exploratória, não causal; GOSLON extraído de pasta; conflitos excluídos da tendência.","Tabela 10",[m,key])
table("correlacoes","Associações exploratórias com a taxa de falha maior que cinco graus",["Método","Associação","n","Spearman ρ IC95%","p permutação"],rows,"10.000 permutações bilaterais e bootstrap de conteúdos. Sem ajuste de multiplicidade; não demonstra causa ou acurácia de GOSLON.")
# Afirmações de contexto e limitações, também com localização exata.
for source,keys,statement,unit,caveat in [
 ("inventario_resumo.json",["stl"],"Inventário inicial: 158 STL, 139 conteúdos de arquivo e 76 diretórios com STL","arquivo STL e diretório","Não confundir arquivo ou diretório com paciente ou conteúdo de par."),
 ("etapa7/status.json",["IDs"],"Análise geométrica: 69 IDs, 64 conteúdos de par","ID e conteúdo de par","Hashes não confirmam identidade clínica."),
 ("etapa7b/protocolo.json",["unique_content_primary"],"63 conteúdos elegíveis para o modelo substituto","conteúdo geométrico único","Identidade clínica não é confirmada pelo hash."),
 ("etapa7b/protocolo.json",["group_counts"],"Grupos do substituto: 27, 13 e 23 conteúdos","conteúdo geométrico único","Rótulos extraídos de pasta; não auditados clinicamente."),
 ("etapa7b/protocolo.json",["five_class"],"Cinco classes GOSLON não treinadas: classe 5 com quatro conteúdos","conteúdo geométrico único","Grupos 1–3 não foram convertidos em GOSLON 1–5."),
 ("etapa7b/protocolo.json",["limitations","1"],"CV da cadeia completa não independente: banco geométrico global pode incluir templates em teste","cadeia de processamento","Não apresentar como generalização externa."),
 ("etapa7/status.json",["classification_metrics_computed"],"Goslon AI não avaliado; modelo treinado indisponível","experimento","Não citar acurácia do Goslon AI."),
 ("etapa8/status.json",["landmarks_humanos_criados"],"Nenhuma marcação humana ou validação anatômica concluída","marcação humana","ICC e dispersão anatômica reais não disponíveis."),
 ("etapa8/status.json",["Slicer_native_test"],"Scripts Slicer sem teste nativo: aplicativo ausente","ferramenta","Testes sintéticos não validam operação no Slicer."),
 ("etapa4/divisao.json",["seed"],"Divisão geométrica original: seed 20261106; 20/49 IDs","ID e conteúdo-paciente","São 17/47 conteúdos; holdout interno previamente estudado."),
 ("etapa4/congelamento.json",["utc"],"Congelamento das variantes antes da avaliação da etapa: 2026-11-05T17:08:05.537882+00:00","protocolo","Hash/data documentam o estado registrado; não constituem carimbo temporal externo."),
 ("etapa4/escolhas.json",[],"Configurações selecionadas no desenvolvimento, sem retunar no teste","protocolo","Etapa 10 apenas consolida; não seleciona novo vencedor."),
 ("etapa4/resultados/oraculos292_resumo.json",["n_cases"],"292 falhas históricas na inicialização conhecida; 58 IDs e 55 conteúdos","casos repetidos condicionados à falha","Não são 292 pacientes nem amostra não selecionada."),
 ("etapa4/resultados/oraculos292_resumo.json",["dominant_axis_case_counts"],"Entre 292 casos: vertical 175; AP 71; lateral 46","caso repetido condicionado à falha","Frame histórico P063; não misturar com frame P016."),
 ("etapa4/resultados/oraculos292_resumo.json",["content_balanced_energy_share"],"Fração de energia dos 292 casos: vertical 47,39%; AP 28,95%; lateral 23,65%","conteúdo-paciente condicionado à falha","Dominância geométrica não prova causa anatômica."),
 ("etapa7b/residuos_pose.json",["2"],"Multi5 no substituto: resíduo realista mediano 2,91°, IQR 1,73–4,63°","ensaios repetidos, resumo descritivo","Não confundir mediana de ensaios com média das medianas por conteúdo das Etapas 4/5."),
 ("etapa3/resultados/resumo.json",["test","porta"],"Porta antiga: 778 de 980 execuções rejeitadas, 79,39%","execução repetida, não paciente","Somente registro histórico; não usada como filtro nem recalibrada.",),
 ("etapa9/status.json",["tests_passed"],"Protótipo local: 13 testes passaram","teste de software","Não é validação clínica, avaliação do classificador nem auditoria LGPD."),
 ("etapa9/status.json",["classifier"],"Protótipo usa stub; nenhuma classe estimada","implementação","Modelo substituto não integrado automaticamente.")]:
 claim(statement,source,unit,caveat,"Metodologia, síntese e pendências",keys)
# Estilo de figuras de impressão, cor distinguível também por linha/marcador.
plt.rcParams.update({"font.family":"DejaVu Serif","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.alpha":.2,"pdf.fonttype":42,"svg.fonttype":"none","svg.hashsalt":"etapa10","savefig.facecolor":"white"})
def figure(slug,title,fig,note):
 n=len(figures)+1;filename=f"{n:02d}_{slug}"
 for ax in fig.axes:
  if not ax.get_xticklabels() or not any("Grupo" in t.get_text() or "Látero" in t.get_text() or "Vertical" in t.get_text() for t in ax.get_xticklabels()):
   ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f"{x:g}".replace(".",",")))
  ax.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f"{x:g}".replace(".",",")))
 fig.savefig(ROOT/"figuras"/(filename+".pdf"),bbox_inches="tight",metadata={"Author":"Autoria do estudo","Title":title,"Creator":"Etapa 10","CreationDate":None,"ModDate":None})
 fig.savefig(ROOT/"figuras"/(filename+".svg"),bbox_inches="tight",metadata={"Creator":"Etapa 10","Date":None})
 fig.savefig(ROOT/"figuras"/(filename+".png"),dpi=300,bbox_inches="tight");plt.close(fig)
 cap=f"Figura {n} – {title}\n\nFonte: elaboração própria.\nNota: {note}\n"
 (ROOT/"figuras"/(filename+"_legenda.txt")).write_text(cap)
 figures.append({"numero":n,"titulo":title,"arquivo":filename,"nota":note})
s="etapa4/resultados/CDF.json";cdf=load(s)
fig,axs=plt.subplots(1,2,figsize=(8,3.5),layout="constrained")
for ax,limit in zip(axs,[15,180]):
 for m,ls in zip(MAIN,["-","--","-."]):
  d=cdf["test"][m];x=np.array(d["x"]);y=np.array(d["cdf_patient_content_mean"])
  ax.plot(x,100*y,label=LABEL[m],ls=ls,color=COLORS[m]);ax.fill_between(x,100*np.array(d["CI95_low"]),100*np.array(d["CI95_high"]),color=COLORS[m],alpha=.09)
 ax.set(xlim=(0,limit),ylim=(0,102),xlabel="Erro angular (graus)",ylabel="Proporção acumulada (%)");ax.axvline(5,color="#aaaaaa",lw=.8)
axs[0].legend(fontsize=8,loc="lower right")
figure("cdf_erro","Distribuição acumulada do erro de consistência no teste interno",fig,"47 conteúdos; peso igual entre conteúdos após agregação de aliases. Bandas IC95% pontuais arquivadas (2.000 bootstraps); não simultâneas. Referência não perturbada de cada método; não anatomia verdadeira. Dois painéis mostram detalhe e cauda completa.")
for m in MAIN:claim(f"CDF teste {LABEL[m]} e bandas pontuais de IC95%",s,"47 conteúdos-paciente",GEOM+" Bandas pontuais, não simultâneas.","Figura 1",["test",m])
fig,axs=plt.subplots(1,2,figsize=(8,3.5),layout="constrained")
for ax,subset in zip(axs,["dev","test"]):
 for j,m in enumerate(MAIN):
  z=[r for r in axisrows if r["conjunto"]==subset and r["metodo"]==m];x=np.arange(3)+(j-1)*.22;y=np.array([r["media_medianas_abs_graus"] for r in z]);lo=np.array([r["IC95_inf"] for r in z]);hi=np.array([r["IC95_sup"] for r in z])
  ax.errorbar(x,y,yerr=[y-lo,hi-y],fmt=["o","s","^"][j],capsize=3,color=COLORS[m],label=LABEL[m])
 ax.set(xticks=np.arange(3),xticklabels=["Látero lateral","AP","Vertical"],ylabel="Média das medianas absolutas (graus)",title="Desenvolvimento" if subset=="dev" else "Teste interno");ax.set_ylim(bottom=0)
axs[0].legend(fontsize=8)
figure("erro_eixos","Erro de rotação por componente no referencial geométrico",fig,"Log SO(3), não ângulos de Euler. 17/47 conteúdos, IC95% por conteúdo calculados apenas para apresentação na Etapa 10 (B=10.000; seed 20261130). Eixos não validados clinicamente.")
fig,ax=plt.subplots(figsize=(7.5,3.5),layout="constrained")
for j,m in enumerate(["controle","anatomica","multi5_rmse"]):
 y=np.array([groups[m][g]["failure5"]["estimate"]*100 for g in ["1","2","3"]]);lo=np.array([groups[m][g]["failure5"]["CI95"][0]*100 for g in ["1","2","3"]]);hi=np.array([groups[m][g]["failure5"]["CI95"][1]*100 for g in ["1","2","3"]]);ax.errorbar(np.arange(3)+(j-1)*.15,y,yerr=[y-lo,hi-y],fmt=["o","s","^"][j],capsize=4,label=LABEL[m],color=COLORS["pca_controle" if m=="controle" else m])
ax.set(xticks=np.arange(3),xticklabels=["Grupo 1 (n=21)","Grupo 2 (n=10)","Grupo 3 (n=16)"],ylabel="Taxa de erro >5° (%)",ylim=(0,60));ax.legend(fontsize=9)
figure("estratos_grupo","Falha de consistência por grupo no teste interno",fig,"IC95% por conteúdo-paciente dentro do grupo; 10.000 reamostragens. Rótulos de nomes de pasta, sem validação clínica. Associação entre grupo e falha não prova causalidade.")
fig,axs=plt.subplots(1,3,figsize=(10,3.3),layout="constrained")
for ax,axis in zip(axs,["vertical","anteroposterior","lateral"]):
 for model,ls,col,mark in zip(["substituto_canonico","substituto_aug10","substituto_aug20"],["-","--","-."],["#222","#777","#007c83"],["o","s","^"]):
  rr=sorted([r for r in metrics if r["condicao"]=="rotation" and r["normalizacao"]=="nenhuma" and r["modelo"]==model and r["eixo"]==axis],key=lambda r:float(r["angulo"]));x=[0]+[float(r["angulo"]) for r in rr];y=[0]+[100*float(r["taxa_troca"]) for r in rr];lo=[0]+[100*float(r["taxa_troca_IC95_inf"]) for r in rr];hi=[0]+[100*float(r["taxa_troca_IC95_sup"]) for r in rr];ax.plot(x,y,label=LABEL[model],ls=ls,color=col,marker=mark,ms=3);ax.fill_between(x,lo,hi,color=col,alpha=.08)
 ax.axhline(5,color="#aaa",ls=":",lw=.8);ax.axhline(10,color="#aaa",ls="--",lw=.8);ax.set(title={"vertical":"Vertical","anteroposterior":"Anteroposterior","lateral":"Látero lateral"}[axis],xlabel="Rotação aplicada (graus)",ylabel="Troca de predição (%)",xticks=[0,2,5,10,20],ylim=(0,75))
axs[0].legend(fontsize=7)
figure("tolerancia_substituto","Sensibilidade à pose do modelo substituto sem normalização",fig,"MODELO SUBSTITUTO, não Goslon AI. 63 conteúdos OOF; sinais ± agregados por conteúdo. Faixas IC95% pontuais de 10.000 bootstraps, sem retreino. Linhas apenas conectam ângulos medidos; não estimam cruzamento contínuo. Comparar acurácia e F1, pois predição constante também pode ter troca zero. Banco geométrico global limita independência da cadeia.")
writecsv(ROOT/"registro_afirmacoes.csv",claims)
# Registro legível: narrativa longa mantida fora das tabelas de resultados.
text="# Registro de afirmações para o TCC\n\nEscopo fechado: resultados das tabelas e figuras deste pacote e afirmações de contexto abaixo. Novas afirmações no TCC devem ser acrescentadas ao registro. Não há afirmação de correção anatômica ou desempenho do Goslon AI.\n\n"
for c in claims:
 text+=f'### {c["afirmacao_ID"]}\n\n{c["afirmacao"]}\n\nFonte: `{c["arquivo_origem"]}`, linha {c["linha"]}, localizador `{c["localizador"]}`. Cópia auditável: `{c["copia_auditavel"]}`. Unidade: {c["unidade_analise"]}. Ressalva obrigatória: {c["ressalva_obrigatoria"]}\n\n'
(ROOT/"registro_afirmacoes.md").write_text(text)
(ROOT/"catalogo.json").write_text(json.dumps({"tabelas":tables,"figuras":figures,"afirmacoes":len(claims)},ensure_ascii=False,indent=2)+"\n")
# HTML imprimível com convenções ABNT/IBGE; não se declara conformidade institucional automática.
h='<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Resultados para o TCC</title><style>@page{size:A4 landscape;margin:2cm 2cm 2cm 3cm}body{font-family:"Times New Roman",serif;font-size:11pt;color:#000}section{break-after:page}h1{font-size:16pt}h2{font-size:12pt;font-weight:normal}table{width:100%;border-collapse:collapse;border-top:1.5px solid;border-bottom:1.5px solid}th{border-bottom:1px solid;font-weight:normal}th,td{padding:7px;text-align:left}small,p.note{font-size:10pt}img{max-width:95%;max-height:15cm} .numeric{white-space:nowrap}</style><body><h1>Figuras e tabelas para o TCC</h1><p>Consistência geométrica e modelo substituto. Rascunho para revisão da orientadora. As legendas e notas são parte inseparável de cada resultado.</p>'
for t in tables:
 h+=f'<section><h2>Tabela {t["numero"]} – {html.escape(t["titulo"])}</h2><table><thead><tr>'+ "".join("<th>"+html.escape(c)+"</th>" for c in t["colunas"])+"</tr></thead><tbody>"
 for row in t["linhas"]:h+="<tr>"+"".join("<td>"+html.escape(str(x))+"</td>" for x in row)+"</tr>"
 h+="</tbody></table><p class=note>Fonte: elaboração própria, conforme registro de afirmações.<br>Nota: "+html.escape(t["nota"])+"</p></section>"
for f in figures:h+=f'<section><h2>Figura {f["numero"]} – {html.escape(f["titulo"])}</h2><img src="figuras/{f["arquivo"]}.svg"><p class=note>Fonte: elaboração própria.<br>Nota: {html.escape(f["nota"])}</p></section>'
(ROOT/"resultados_ABNT.html").write_text(h+"</body></html>")
print(f"Gerados: {len(tables)} tabelas, {len(figures)} figuras, {len(claims)} afirmações")
