from pathlib import Path
import json,csv,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OLD=ROOT/"etapa7b";OUT=OLD/"correcoes_v2";R=OUT/"resultados"
def load(p):return json.loads(Path(p).read_text())
def read(name):return list(csv.DictReader((R/name).open()))
def write(name,rows):
 with (R/name).open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def fmt(x,n=2):return f"{float(x):.{n}f}".replace(".",",")
def ci(r,k,scale=1):return f'{fmt(float(r[k])*scale)} [{fmt(float(r[k+"_IC95_inf"])*scale)}; {fmt(float(r[k+"_IC95_sup"])*scale)}]'
def delta(r):return f'{fmt(100*float(r["diferenca"]))} [{fmt(100*float(r["IC95_inf"]))}; {fmt(100*float(r["IC95_sup"]))}]'
def main():
 metrics=read("metricas_IC95.csv");contrasts=read("contrastes_pareados_IC95.csv");primary=load(R/"desfecho_primario.json");labels=load(R/"rotulos_resumo.json");frame=read("enquadramento_realista.csv")
 ownrows=read("rotacoes_referencia_proprio_ramo.csv");ownsummary=[];bank={"P016","P004","P045","P029","P002"}
 for population in ["todos_63","sem_templates_58"]:
  cells={}
  for r in ownrows:
   if population=="sem_templates_58" and r["ID"] in bank:continue
   cells.setdefault((r["modelo"],r["eixo"],float(r["angulo"])),[]).append(r)
  for (model,axis,deg),rr in sorted(cells.items()):
   rr=sorted(rr,key=lambda r:r["ID"]);assert len({r["ID"] for r in rr})==len(rr)
   values=np.array([float(r["taxa_troca_vs_zero_centralizado"]) for r in rr]);w=np.random.default_rng(20261121).multinomial(len(rr),[1/len(rr)]*len(rr),size=10000)/len(rr);low,high=np.quantile(w@values,[.025,.975])
   ownsummary.append({"populacao":population,"modelo":model,"eixo":axis,"angulo":deg,"n_conteudos":len(rr),"taxa_troca":float(values.mean()),"IC95_inf":float(low),"IC95_sup":float(high),"referencia":"predicao canonica centralizada a 0 graus","unidade":"conteudo-paciente","carater":"exploratorio"})
 write("rotacoes_proprio_ramo_IC95.csv",ownsummary)
 # Mapa explícito de unidades, incluindo os arquivos históricos que não foram reescritos.
 units=[
 {"fonte":"etapa4/resultados/bootstrap_resumo.json: nominal_IDs","unidade_estimando":"ID fisico","unidade_bootstrap":"ID com 20 ensaios em bloco","n":"20 dev / 49 teste","observacao":"Estimando nominal secundario; nao usar seus pontos junto dos IC por conteudo."},
 {"fonte":"etapa4/resultados/bootstrap_resumo.json: content_cluster_bootstrap","unidade_estimando":"conteudo-paciente","unidade_bootstrap":"conteudo, medias de resumos dentro dos aliases","n":"17 dev / 47 teste","observacao":"Estimando conservador principal; ponto pode diferir do nominal."},
 {"fonte":"etapa4/resultados/bootstrap_contrastes*.json","unidade_estimando":"diferenca pareada por conteudo-paciente","unidade_bootstrap":"mesmos conteudos para ambos os metodos","n":"17 dev / 47 teste","observacao":"Codigo analisar.py usa draws_cluster; nao e contraste dos 20/49 IDs nominais."},
 {"fonte":"etapa5/resultados/estratos_bootstrap.json e contrastes balanceados","unidade_estimando":"conteudo-paciente dentro do grupo","unidade_bootstrap":"conteudo, aliases agregados antes","n":"47 total; 21/10/16 por grupo","observacao":"Metrica median_error_deg e media das medianas individuais; mediana das medianas tem arquivo separado."},
 {"fonte":"etapa5/resultados/diferencas_pareadas_por_divisao.json","unidade_estimando":"conteudo-paciente em cada divisao","unidade_bootstrap":"conteudos pareados dentro da divisao","n":"variavel por divisao","observacao":"Dez divisoes sobrepostas; nao dez estudos independentes."},
 {"fonte":"etapa7b/metricas_IC95.csv e diferencas_pareadas_IC95.csv historicos","unidade_estimando":"conteudo-paciente","unidade_bootstrap":"63 representantes unicos; sinais/ensaios em bloco","n":"63","observacao":"Coluna ID e representante de um hash de par, nao todos os 69 IDs; media entre conteudos."},
 {"fonte":"etapa7b/sensibilidade_sem_templates.csv historico","unidade_estimando":"conteudo-paciente; somente condicao canonica","unidade_bootstrap":"58 representantes fora do banco","n":"58","observacao":"Sensibilidade anterior limitada; substituida pela comparacao completa nesta extensao."},
 {"fonte":"correcoes_v2/resultados/contrastes_pareados_IC95.csv","unidade_estimando":"diferenca pareada por conteudo-paciente","unidade_bootstrap":"conteudo; preserva sinais e 20 repeticoes","n":"63 ou 58, explicitado por linha","observacao":"Nunca bootstrap de ensaios isolados; primario e unico contraste marcado."},
 {"fonte":"correcoes_v2/resultados/sensibilidade_templates_todas_condicoes.csv","unidade_estimando":"conteudo-paciente","unidade_bootstrap":"conteudos dentro da populacao 63 ou 58","n":"63 e 58","observacao":"Diferenca 58 menos 63 e descritiva de composicao, sem IC de amostras independentes."},
 {"fonte":"etapa10/tabelas/01_... e 02_...; 03_contrastes.csv; 06_eixos.csv","unidade_estimando":"conteudo-paciente","unidade_bootstrap":"17/47 conteudos","n":"17 dev / 47 teste","observacao":"Componentes novos ponderam conteudo; diferem de medias por ID no resumo historico da Etapa 4."}]
 write("unidades_contrastes.csv",units)
 glossary=[{"rotulo_antigo":"falha >5 graus ou falha_5","rotulo_correto":"proporcao com erro de consistencia de pose estritamente maior que 5 graus","unidade_valor":"fracao 0-1; porcentagem somente apos multiplicar por 100","nao_significa":"falha clinica, incorrecao anatomica ou erro de classificacao"},
 {"rotulo_antigo":"falha >10 graus ou falha_10","rotulo_correto":"proporcao com erro de consistencia de pose estritamente maior que 10 graus","unidade_valor":"fracao 0-1; porcentagem somente apos multiplicar por 100","nao_significa":"falha clinica ou troca de classe"},
 {"rotulo_antigo":"limiar troca maior 5/10","rotulo_correto":"primeiro angulo testado com taxa de troca de predicao estritamente maior que 5% ou 10%","unidade_valor":"angulo em graus; taxa em porcentagem","nao_significa":"erro angular maior que 5 ou 10 graus"},
 {"rotulo_antigo":"median_error_deg em estratos Etapa5","rotulo_correto":"media entre conteudos das medianas individuais do erro","unidade_valor":"graus","nao_significa":"mediana dos ensaios ou mediana entre conteudos"},
 {"rotulo_antigo":"por paciente nos arquivos Etapa7B","rotulo_correto":"por conteudo-paciente, representado por um unico ID","unidade_valor":"conteudo geometrico de par","nao_significa":"identidade clinica confirmada nem todos os aliases como observacoes independentes"}]
 write("glossario_rotulos.csv",glossary)
 text="# Etapa 7B corrigida com centralização e sensibilidade aos templates\n\n**MODELO SUBSTITUTO; nenhum resultado se refere ao Goslon AI.** Câmeras originais PLACEHOLDER. Tudo local, cópias e IDs. Não se demonstra correção anatômica.\n\n"
 text+="## Plano registrado e desfecho primário\n\nO protocolo desta extensão foi registrado antes das novas features/predições centralizadas. Os resultados antigos já eram conhecidos: este é um primário da extensão, não um pré-registro retrospectivo do estudo original. `protocolo.json`, `congelamento.json`, `registro_analise_preexecucao.json` e `congelamento_analise.json` preservam essa sequência. Todos os demais resultados são exploratórios, IC95% pontuais sem ajuste por multiplicidade.\n\n"
 text+="Primário: diferença multi5_rmse menos apenas centralizado na taxa de troca versus a predição canônica original multi5 do substituto canônico, nos 20 ensaios realistas de cada um dos **58 conteúdos fora do banco**, com peso igual e bootstrap pareado de conteúdos (10.000; seed 20261121).\n\n"
 text+=f'**Resultado: {delta(primary)} pontos percentuais, IC95%.** '+("O IC exclui zero neste contraste previamente declarado da extensão; a inferência continua condicionada aos modelos/dados locais." if float(primary["IC95_inf"])*float(primary["IC95_sup"])>0 else "O IC inclui zero; não estabelece diferença neste contraste.")+" Fonte: `resultados/desfecho_primario.json`. Não é efeito causal exclusivamente angular: registro completo também ajusta translação.\n\n"
 text+="## Apenas centralizado\n\nA operação estima da geometria observada o centroide superficial de cada arcada, ponderado por área, e leva a média desses dois centroides à origem das câmeras por uma translação única. R é identidade. Orientação, escala, câmeras e material ficam intactos; nenhum rótulo, template ou Q verdadeiro entra nesse estimador. São 51 condições novas por conteúdo: pose canônica centralizada, 30 rotações controladas e 20 realistas.\n\n"
 text+="A predição canônica original multi5 continua como referência comum da troca, inclusive no primário. Também foi guardada a referência da pose centralizada em 0° para examinar rotações sem confundir o recentramento inicial com mudança de orientação (`rotacoes_referencia_proprio_ramo.csv`). Ruído e recorte permanecem apenas nas nuvens de registro dos métodos completos; a superfície renderizada é a malha decimada íntegra, como no experimento original. O centralizador usa essa geometria observada, não uma reconstrução inventada da superfície recortada.\n\n"
 center0=next(r for r in metrics if r["populacao"]=="sem_templates_58" and r["modelo"]=="substituto_canonico" and r["condicao"]=="canonical" and r["normalizacao"]=="centralizado")
 text+=f'Só recentrar a pose de 0° já muda {fmt(100*float(center0["taxa_troca"]))}% das predições nos 58 conteúdos. A curva versus a referência original inclui esse deslocamento de enquadramento; `rotacoes_proprio_ramo_IC95.csv` apresenta também a troca versus o próprio zero centralizado, com IC por conteúdo.\n\n'
 for pop,title in [("sem_templates_58","58 conteúdos fora do banco"),("todos_63","63 conteúdos elegíveis")]:
  text+=f"### Ensaios realistas com {title}\n\n| Condição | Acurácia % IC95 | F1 macro IC95 | Erro ordinal de grupo IC95 | Troca % IC95 |\n|---|---:|---:|---:|---:|\n"
  for method in ["nenhuma","centralizado","controle","anatomica","multi5_rmse"]:
   r=next(r for r in metrics if r["populacao"]==pop and r["modelo"]=="substituto_canonico" and r["condicao"]=="realistic" and r["normalizacao"]==method)
   text+=f'| {method} | {ci(r,"acuracia",100)} | {ci(r,"f1_macro")} | {ci(r,"erro_ordinal_grupo")} | {ci(r,"taxa_troca",100)} |\n'
  text+="\nFonte: `resultados/metricas_IC95.csv`; unidade = conteúdo-paciente, não ensaio. Valores históricos são preservados; nesta extensão os IC foram recalculados com a seed declarada, portanto podem ter pequenas diferenças de Monte Carlo em relação aos IC antigos.\n\n"
 text+="### Recuperação de enquadramento\n\n| Condição | Vistas vazias / total | % vazias |\n|---|---:|---:|\n"
 for r in frame:text+=f'| {r["normalizacao"]} | {r["vistas_vazias"]}/{r["n_vistas"]} | {fmt(100*float(r["fracao_vazias"]))} |\n'
 text+="\nFonte: `resultados/enquadramento_realista.csv`, 63 conteúdos. São contagens descritivas de vistas repetidas, não tamanho amostral independente. Centralizar permite distinguir operacionalmente enquadramento de registro da pose, sem afirmar que todo contraste restante seja um efeito angular isolado.\n\n"
 c=next(r for r in contrasts if r["populacao"]=="sem_templates_58" and r["modelo"]=="substituto_canonico" and r["condicao"]=="realistic" and r["metodo"]=="centralizado" and r["referencia"]=="nenhuma" and r["metrica"]=="taxa_troca")
 text+=f'Exploratório, 58 conteúdos: apenas centralizado menos nenhuma normalização na taxa de troca = {delta(c)} p.p. A recuperação de enquadramento não se traduziu em redução demonstrada da taxa de troca nesse contraste. Não atribuir ao enquadramento toda a diferença anterior entre nenhuma normalização e registro completo.\n\n'
 text+="## Banco e sensibilidade\n\nNão foi apresentado um banco global como se tivesse sido treinado dentro de cada fold. A alternativa permitida foi aplicada: **retirar os cinco conteúdos-template apenas da pontuação e recomputar todas as condições**, comparando 63 e 58 conteúdos, com IC e contraste pareado dentro de cada população. O arquivo `sensibilidade_templates_todas_condicoes.csv` inclui todos os modelos, eixos, ângulos, condições e métricas; a versão anterior cobria somente a condição canônica. A exclusão é por conteúdo e inclui aliases, não por nome de arquivo.\n\n"
 text+="Isso não remove a exposição geométrica prévia do normalizador, não retreina as cabeças e não valida de forma independente a cadeia completa. Um banco só do treino de cada fold mudaria as imagens canônicas; seria necessário reconstruir e treinar novamente essa cadeia em um novo experimento. Os cinco templates podem continuar participando do treino das cabeças do protocolo original; sua remoção aqui é somente da pontuação. As populações 58 e 63 são aninhadas e sua diferença é de composição, não um efeito causal de independência.\n\n"
 text+="## Rótulos divergentes por conteúdo\n\n"
 text+=f'Entre {labels["IDs"]} IDs e {labels["conteudos"]} conteúdos, há **{labels["conteudos_com_conflito_grupo"]} conteúdo com conflito de grupo**, **{labels["conteudos_com_conflito_GOSLON"]} com conflito GOSLON** e **{labels["conteudos_com_qualquer_conflito"]} com qualquer conflito**, envolvendo {labels["IDs_nesses_conteudos"]} IDs. As contagens de tipos podem se sobrepor.\n\n| Conteúdo | IDs e rótulos | Grupo divergente | GOSLON divergente |\n|---|---|---|---|\n'
 for r in read("divergencias_rotulos.csv"):text+=f'| {r["ID_conteudo"]} | {r["rotulos_por_ID"]} | {r["conflito_grupo"]} | {r["conflito_GOSLON"]} |\n'
 text+="\nTodos os 69 rótulos por ID estão em `rotulos_por_ID.csv`, e todos os 64 blocos em `auditoria_conteudos.csv`. Conflito entre cópias é diferente de incompatibilidade presumida entre grupo e GOSLON. Não houve correção automática. P021/P039 continuam excluídos da tarefa de grupos; conflito GOSLON em grupo consistente não foi reinterpretado como classe GOSLON.\n\n"
 text+="## Unidade de análise e contrastes\n\nO arquivo `unidades_contrastes.csv` reconcilia os arquivos históricos e atuais. Na Etapa 7B, cada ID pontuado é um representante único de conteúdo, não cada pasta física. Todos os contrastes da extensão agregam primeiro as repetições dentro desse conteúdo, usam os mesmos conteúdos nos dois ramos e só depois calculam a média e o bootstrap pareado. F1 macro é calculado na matriz do conjunto e não por uma pessoa.\n\nNa Etapa 4 coexistem resumos nominais por 20/49 IDs e por 17/47 conteúdos; os contrastes arquivados usam **conteúdos**, não os IDs nominais. Na Etapa 5, estratos e contrastes usam conteúdo. As tabelas principais da Etapa 10 também usam conteúdo; os eixos de apresentação com peso por conteúdo podem diferir da média nominal de componentes por ID apresentada historicamente. Não combinar um ponto por ID com um IC por conteúdo.\n\n"
 text+="## Rotulagem corrigida\n\nOs novos arquivos usam `proporcao_erro_consistencia_pose_maior_5_graus` e `..._10_graus`, com comparação estrita (>), em vez de sugerir falha anatômica, clínica ou classificatória. Os valores brutos são frações; converter para porcentagem somente na apresentação. Taxa de troca >5% ou >10% é outra grandeza: o limiar é o primeiro ângulo testado em que a porcentagem de predições trocadas excede esse valor. `glossario_rotulos.csv` preserva a correspondência dos nomes históricos, que não foram reescritos silenciosamente.\n\n"
 text+="## Reprodução e limites\n\nExecutar, a partir da raiz, `etapa1/.venv/bin/python etapa7b/correcoes_v2/scripts/extrair.py --workers 6`, depois `avaliar_correcao.py` e `gerar_relatorio.py` no mesmo diretório de scripts. Usar aspas nos caminhos. A extração verifica os hashes congelados; os pesos são carregados somente do disco local, com `weights=None` na construção da arquitetura. Nenhum download, upload, alteração dos originais ou push para Git faz parte desta extensão.\n\n"
 text+="As 15 cabeças congeladas foram reutilizadas sem treino. Os baselines logística/maioria foram reconstruídos com o treino original e suas cinco predições canônicas por conteúdo foram conferidas contra o arquivo anterior, incluindo as três cabeças. IC condicionam a essas predições fixas, sem retreino ou incerteza de outra população. Rótulos não são validados clinicamente; câmeras originais são desconhecidas; não há validação externa, anatomia verdadeira ou resultado do Goslon AI.\n"
 (OUT/"README.md").write_text(text)
 # Figuras científicas com unidades e distinção entre primário e exploratório.
 import matplotlib;matplotlib.use("Agg")
 import matplotlib.pyplot as plt
 plt.rcParams.update({"font.family":"DejaVu Serif","font.size":10,"axes.spines.top":False,"axes.spines.right":False})
 fig,axs=plt.subplots(1,2,figsize=(10,4),layout="constrained")
 methods=["nenhuma","centralizado","controle","anatomica","multi5_rmse"]
 for ax,metric in zip(axs,["acuracia","taxa_troca"]):
  for j,pop in enumerate(["todos_63","sem_templates_58"]):
   rr=[next(r for r in metrics if r["populacao"]==pop and r["modelo"]=="substituto_canonico" and r["condicao"]=="realistic" and r["normalizacao"]==m) for m in methods];y=np.array([100*float(r[metric]) for r in rr]);lo=np.array([100*float(r[metric+"_IC95_inf"]) for r in rr]);hi=np.array([100*float(r[metric+"_IC95_sup"]) for r in rr]);ax.errorbar(np.arange(5)+(j-.5)*.14,y,yerr=[y-lo,hi-y],fmt=["o","^"][j],capsize=3,label={"todos_63":"63 conteúdos","sem_templates_58":"58 fora do banco"}[pop])
  ax.set(xticks=np.arange(5),xticklabels=["Sem norm.","Só centro","PCA","Orientada","Multi5"],ylabel={"acuracia":"Acurácia (%)","taxa_troca":"Troca de predição (%)"}[metric],ylim=(0,100));ax.tick_params(axis="x",labelrotation=25);ax.grid(alpha=.2);ax.legend(fontsize=8)
 fig.suptitle("MODELO SUBSTITUTO — ensaios realistas; IC95% por conteúdo")
 for ext in ["png","pdf"]:fig.savefig(R/("comparacao_realista."+ext),dpi=300,bbox_inches="tight")
 plt.close(fig)
 fig,axs=plt.subplots(1,3,figsize=(11,3.6),layout="constrained")
 for ax,axis in zip(axs,["vertical","anteroposterior","lateral"]):
  for method,style in [("nenhuma","--"),("centralizado","-"),("multi5_rmse","-.")]:
   rr=sorted([r for r in metrics if r["populacao"]=="sem_templates_58" and r["modelo"]=="substituto_canonico" and r["condicao"]=="rotation" and r["normalizacao"]==method and r["eixo"]==axis],key=lambda r:float(r["angulo"]));ax.plot([float(r["angulo"]) for r in rr],[100*float(r["taxa_troca"]) for r in rr],ls=style,marker="o",label={"nenhuma":"Sem norm. / ref. original","centralizado":"Só centro / ref. original","multi5_rmse":"Multi5 / ref. original"}[method])
  rr=sorted([r for r in ownsummary if r["populacao"]=="sem_templates_58" and r["modelo"]=="substituto_canonico" and r["eixo"]==axis],key=lambda r:r["angulo"])
  ax.plot([r["angulo"] for r in rr],[100*r["taxa_troca"] for r in rr],ls=":",color="black",marker="s",ms=3,label="Só centro / próprio zero")
  ax.set(title=axis,xlabel="Rotação (graus)",ylabel="Troca de predição (%)",ylim=(0,80),xticks=[2,5,10,20]);ax.grid(alpha=.2)
 axs[0].legend(fontsize=6.7);fig.suptitle("MODELO SUBSTITUTO — 58 conteúdos; análise exploratória")
 for ext in ["png","pdf"]:fig.savefig(R/("rotacoes_centralizado."+ext),dpi=300,bbox_inches="tight")
 plt.close(fig)
 print("Relatorio, glossario, unidades e figuras da correcao gerados.")
if __name__=="__main__":main()
