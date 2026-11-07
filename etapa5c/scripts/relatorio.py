"""Consolida resultados congelados; não treina, escolhe parâmetros ou abre novos testes."""
from pathlib import Path
import csv,json,hashlib,datetime,platform,importlib.metadata
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]; O=ROOT/"etapa5c"; R=O/"resultados"
def read(path):
 with Path(path).open() as f:return list(csv.DictReader(f))
def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fmt(x):return f"{float(x):.3f}".replace(".",",")
def ci(r,k,percent=False):
 factor=100 if percent else 1
 a,b,c=[float(r[k+s])*factor for s in ["","_IC95_inf","_IC95_sup"]]
 return f"{fmt(a)} [{fmt(b)}; {fmt(c)}]"
def table(headers,rows):
 return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join(["---"]*len(headers))+" |"]+["| "+" | ".join(map(str,r))+" |" for r in rows])
names={"substituto_canonico":"Modelo substituto","logistica_descritores":"Logística de descritores","majoritaria":"Classe majoritária"}
methods={"nenhuma":"Sem normalização","centralizado":"Só centralização","controle":"Controle PCA + ICP","anatomica":"Regra anatômica + ICP","multi5_rmse":"multi5_rmse"}
sizes=read(O/"tamanhos.csv"); metrics=read(R/"metricas_OOF_IC95.csv"); test=read(R/"metricas_teste_final_IC95.csv"); groups=read(R/"metricas_grupo_teste_IC95.csv")
thresholds=read(R/"tolerancia_OOF.csv"); exclusions=read(O/"exclusoes_rotulos.csv")
freeze=load(O/"congelamento.json"); execution=load(O/"congelamento_execucao.json"); gate=load(O/"liberacao_final.json")
opening=load(O/"teste_bloqueado/abertura.json")
parts=["# Etapa 5C — nova divisão do modelo substituto\n",
"Resultados locais, com identificadores P001…; nenhum envio externo. Modelo substituto de três grupos, não Goslon AI. As câmeras originais continuam PLACEHOLDER; as features reutilizadas usam câmeras próprias congeladas. Não há validação de correção anatômica.\n",
"## Identidade, rótulos e exclusões\n",
"Não foi encontrado um identificador clínico pseudonimizado validado nas fontes locais consultadas no plano prévio. P001… identificam moldes, não comprovam identidade de paciente. A unidade disponível é um paciente proxy: conteúdo do par identificado pela dupla SHA256 das arcadas. Aliases de conteúdo idêntico nunca cruzam conjuntos e não recebem peso independente. Nenhuma regra de normalização recebe grupo ou GOSLON como entrada.\n",
"Foram excluídos dois conteúdos inteiros por conflito de grupo OU GOSLON, sem corrigir o rótulo por conveniência:\n",
table(["ID do conteúdo","IDs excluídos","Grupos","GOSLON"],[[r["ID_conteudo"],r["IDs"],r["grupos"],r["GOSLON"]] for r in exclusions]),
"\nO critério geométrico, sem consultar rótulos, encontrou três pares candidatos na triagem de diferença máxima de 5% em dispersão PCA e área das duas arcadas. Após ICP rígido comum ao par, nenhum atendeu simultaneamente, nas duas arcadas, RMSE simétrico ≤0,50 mm presumidos e P95 bidirecional ≤1,00 mm. A lista de suspeitas está vazia; os três candidatos e distâncias estão em geometria_candidatos.csv. A triagem amostra 10.000 pontos por arcada, seed 20261122, até 40 iterações. Esses limiares são suposições de engenharia para revisão manual, sem validação de identidade. Zero suspeitas não exclui múltiplos moldes ou visitas da mesma pessoa: alterações longitudinais podem escapar. A inferência é por paciente proxy, não por identidade clínica confirmada.\n",
"## Divisão congelada\n",
table(["Conjunto","Grupo 1","Grupo 2","Grupo 3","Total de conteúdos/pacientes proxy"],[[label]+[next(r["n_conteudos"] for r in sizes if r["conjunto"]==key and r["grupo"]==str(g)) for g in [1,2,3,"todos"]] for key,label in [("elegiveis","Elegíveis"),("desenvolvimento","Desenvolvimento"),("teste","Teste bloqueado")]]) if any(r["conjunto"]=="desenvolvimento" for r in sizes) else "",
]
# Nomes de conjunto são preservados como gravados pelo preparador.
parts=[p for p in parts if p]
if not any("Total de conteúdos/pacientes" in p for p in parts):
 rows=[]
 for key in dict.fromkeys(r["conjunto"] for r in sizes):
  if key.startswith("CV"):continue
  rr=[r for r in sizes if r["conjunto"]==key and r["repeticao"]=="-1"]
  if rr:rows.append([key]+[next(x["n_conteudos"] for x in rr if x["grupo"]==str(g)) for g in [1,2,3,"todos"]])
 parts.append(table(["Conjunto","Grupo 1","Grupo 2","Grupo 3","Total de conteúdos/pacientes proxy"],rows))
parts.extend([
"\nSão 62 conteúdos elegíveis (65 IDs físicos após exclusões). O teste tem 16/62 = 25,81%. Atenção: grupo 2 tem somente três pacientes proxy no teste, menos de cinco, com IC muito impreciso. Os tamanhos de cada treino/validação e grupo estão em tamanhos.csv; aliases não são pacientes adicionais.\n",
"Seed do bloqueio: 20261122. Quotas estratificadas por maiores restos (7/3/6), sorteio determinístico por blocos. Restrição declarada antes da execução: os cinco conteúdos do banco global ficam exclusivamente no desenvolvimento. Portanto, a amostragem é estratificada e condicional a essa restrição, não um sorteio irrestrito.\n",
f"SHA256 da divisão: {freeze['sha256_divisao']}. Congelamento UTC: {freeze['utc']}. O hash foi gravado antes das novas análises de desempenho. Os rótulos precisaram ser lidos antes para auditoria de conflitos e estratificação; não se afirma ausência absoluta de leitura prévia de rótulos.\n",
"Este bloqueio vale para a reanálise 5C. Os conteúdos já participaram de análises anteriores; o novo teste não é virgem, externo ou demonstração de generalização independente. Nenhuma decisão desta execução usou desempenho do teste.\n",
"## Validação cruzada e modelo fixo\n",
"No desenvolvimento: StratifiedGroupKFold, quatro folds por seed, cinco seeds 20261123–20261127; 20 ajustes novos e independentes das cabeças anteriores. Cada conteúdo recebe uma predição fora do fold por repetição e condição. Treino apenas na pose canônica, sem nova augmentation. As cinco repetições são medidas repetidas do mesmo paciente proxy.\n",
"Backbone MobileNet V3 Small pré-treinado ImageNet congelado, features locais de seis vistas com 576 dimensões; concatenação 3456 → LayerNorm → Linear64 → GELU → Dropout0,2 → Linear3. Cabeça fixa, 80 épocas, última época, AdamW lr 0,001, weight decay 0,01, batch 8, pesos de classe somente do treino. Seed de ajuste: 20261200 + 1000×repetição + 100×fold (índices iniciados em zero). Não houve seleção de hiperparâmetros nem de época na validação ou no teste desta execução. Baselines: classe majoritária do treino; StandardScaler e regressão logística C=1, class_weight=balanced, max_iter=2000, ajustados somente no treino de cada fold.\n",
"### Templates: alternativa de sensibilidade explicitamente adotada\n",
"Não foi refeito o banco por fold. As features disponíveis foram calculadas em referenciais do banco global; trocar o banco exigiria nova cadeia de imagens/features. Usou-se a alternativa permitida: pontuar o desenvolvimento completo (46 conteúdos) e repetir todas as métricas excluindo da pontuação os cinco conteúdos P016, P004, P045, P029 e P002 (41 conteúdos), conforme exclusoes_sensibilidade_banco.csv. A retirada é da pontuação, não do treino das cabeças. As duas populações usam exatamente os mesmos modelos OOF.\n",
"Na CV, a geometria de um template ainda pode pertencer à validação. A sensibilidade não elimina essa exposição e não equivale a validação da cadeia inteira com templates selecionados apenas no treino de cada fold. No teste final nenhum dos cinco templates está entre os 16 conteúdos avaliados; a exposição histórica permanece. Não são usados rótulos para selecionar templates durante a consulta: a seleção continua por RMSE.\n",
"### Resultados canônicos OOF (exploratórios)\n",
table(["População","Modelo","Acurácia [IC95%]","F1 macro [IC95%]","Erro ordinal grupo [IC95%]"],[[r["populacao"],names[r["modelo"]],ci(r,"acuracia"),ci(r,"f1_macro"),ci(r,"erro_ordinal_grupo")] for r in metrics if r["condicao"]=="canonical" and r["normalizacao"]=="referencia_canonica_multi5"]),
"\nO F1 macro é calculado pela matriz de confusão com as três classes fixas, não como média de um F1 individual. Erro ordinal = |grupo predito − grupo real|; não é erro ordinal GOSLON de cinco classes. Os rótulos GOSLON serviram à auditoria de conflitos, não são o alvo treinado.\n",
"## Tolerância à pose: exclusivamente OOF no desenvolvimento\n",
"Rotações conhecidas de 2°, 3°, 5°, 10° e 20°, três eixos e sinais ±, com sem normalização, centralização apenas, controle, regra anatômica e multi5_rmse. Incluídos os ensaios realistas armazenados nas etapas anteriores. As predições novas usam somente as cabeças treinadas fora do fold; nenhuma curva de pose usa o teste bloqueado.\n",
"A referência de troca é a predição canônica multi5 do próprio modelo e repetição. Centralizar e trocar o normalizador podem mudar a predição mesmo sem uma rotação; esse efeito de enquadramento/referencial faz parte dos contrastes e não deve ser atribuído só ao ângulo. O zero foi medido para sem normalização, centralizado e multi5; não existe zero renderizado específico para controle/regra anatômica nesta cadeia, portanto o primeiro ângulo nesses ramos não identifica uma tolerância angular isolada. Limiares são o primeiro ângulo efetivamente avaliado que excede a taxa, sem interpolação; não uma margem garantida.\n",
table(["População","Método","Eixo","Primeiro ângulo: troca >5%","Primeiro ângulo: troca >10%"],[[r["populacao"],methods[r["normalizacao"]],r["eixo"],r["primeiro_angulo_troca_maior_5_pct"],r["primeiro_angulo_troca_maior_10_pct"]] for r in thresholds if r["modelo"]=="substituto_canonico" and r["eixo"]=="todos"]),
"\nA tabela completa por eixo/modelo está em tolerancia_OOF.csv. As taxas e IC95% de cada condição, eixo e ângulo estão em metricas_OOF_IC95.csv; resumos individuais em resumos_por_paciente_proxy.csv. Contrastes pareados de perturbações realistas e IC95% estão em contrastes_OOF_IC95.csv. Todos são exploratórios, IC pontuais sem correção de multiplicidade. Taxa de troca de classe não é falha angular >5°/10°.\n",
"![Tolerância — apenas OOF](resultados/tolerancia_apenas_OOF.png)\n",
"Nos ensaios de rotação rígida pura, a predição multi5 ficou invariável nesta amostra. Isso é compatível com equivariância do registro nessa perturbação e não demonstra robustez a alterações de superfície, anatomia ou câmera. Os ensaios realistas precisam ser lidos separadamente.\n",
table(["Método — realista, OOF sem banco (41)","Acurácia [IC95%]","Troca (%) [IC95%]"],[[methods[r["normalizacao"]],ci(r,"acuracia"),ci(r,"taxa_troca",True)] for r in metrics if r["populacao"]=="sensibilidade_sem_banco" and r["modelo"]=="substituto_canonico" and r["condicao"]=="realistic"]),
"\nNas perturbações realistas reutilizadas, reamostragem/ruído/recorte afetam as nuvens de registro; o render usa a malha decimada e íntegra. Assim, não se trata de recorte visual completo da entrada. Translações e câmera fixa podem gerar vistas vazias, registradas nas predições; não foram excluídas por desempenho. A referência canônica usada no treino já incorpora a normalização multi5 global.\n",
"## Teste final canônico — modelo substituto\n",
f"Desfecho primário declarado previamente: F1 macro canônico da cabeça fixa. Após concluir OOF, o modelo foi treinado nos 46 conteúdos com seed 20261299. Pesos, baselines e decisões foram congelados em liberacao_final.json às {gate['utc']}, antes da abertura registrada em teste_bloqueado/abertura.json. Avaliação final única, apenas pose canônica; não houve ajuste após observar os resultados.\n",
table(["Modelo","Acurácia [IC95%]","F1 macro [IC95%]","Erro ordinal grupo [IC95%]"],[[names[r["modelo"]],ci(r,"acuracia"),ci(r,"f1_macro"),ci(r,"erro_ordinal_grupo")] for r in test]),
"\nA comparação dos baselines é secundária/exploratória; não se escolheu outro modelo após o teste. O resultado primário encontra-se em primario_teste.json. A amostra pequena e a exposição histórica impedem tratar esse número como acurácia de generalização nova.\n",
table(["Modelo","Grupo","Pacientes proxy","Acurácia [IC95%]","Erro ordinal [IC95%]"],[[names[r["modelo"]],r["grupo"],r["n_pacientes_proxy"],ci(r,"acuracia"),ci(r,"erro_ordinal_grupo")] for r in groups]),
"\nNão se reporta F1 macro dentro de um estrato com uma única classe real; o F1 macro global contempla as três classes. Para grupo 2, n=3 e IC amplo. Não se mudou a seed para obter uma amostra ou resultado melhor.\n",
"![Matrizes do teste canônico](resultados/confusao_teste_canonico.png)\n",
"## Unidade de análise e IC95%\n",
"10.000 reamostragens percentis, seed 20261300, sobre blocos de paciente proxy. Para OOF, primeiro são agregados ensaios/sinais e as cinco repetições dentro de cada conteúdo; aliases pertencem a um só conteúdo. Conteúdos no mesmo bloco geométrico seriam agregados no bloco; nesta triagem não surgiram blocos adicionais. Cada paciente proxy tem o mesmo peso. As matrizes de confusão e métricas são recalculadas em cada bootstrap, mantendo três classes fixas mesmo quando uma classe não aparece em uma reamostragem. Não se reamostram linhas de ensaio, folds ou seeds como pacientes independentes; não se retreinam redes no bootstrap. Portanto o IC é condicional às divisões/modelos fixos e não cobre toda a incerteza de seleção/treino. Por grupo, o bootstrap usa somente os pacientes proxy daquele grupo.\n",
"## Arquivos e reprodução\n",
"- plano_previo.json: critérios anteriores à nova análise.\n- divisao.json e divisao.sha256: IDs e hash do bloqueio; folds_CV.json: 20 partições.\n- congelamento.json: divisão e entradas; congelamento_execucao.json: código e features de desenvolvimento antes do treino; liberacao_final.json: pesos fixos antes de abrir o teste.\n- auditoria_rotulos.csv, exclusoes_rotulos.csv: consistência por ID/conteúdo.\n- geometria_candidatos.csv e suspeitas_mesmo_paciente.csv: triagem geométrica para revisão humana.\n- tamanhos.csv: conjunto, grupo, fold, conteúdos, blocos e IDs físicos.\n- resultados/predicoes_OOF.csv: predições individuais; metricas_OOF_IC95.csv: 642 células com IC.\n- resultados/metricas_teste_final_IC95.csv, metricas_grupo_teste_IC95.csv e confusao_teste_final.csv: resultado final e estratos.\n- qa/verificacao_pre_teste.json e qa/verificacao_final.json: auditorias antes e depois da avaliação, sem sobreposição de conteúdo/bloco.\n- reproducao.json: versões, seeds e hashes; imagens científicas também em PDF.\n",
"Executar somente em cópia de reprodução limpa, preservando os artefatos desta execução. Ordem: preparar.py → congelar_execucao.py (separar manifestos e congelar execução) → classificador.py cv → avaliar.py → verificar.py (pré-teste) → classificador.py final_fit → teste_final.py → verificar.py --final → relatorio.py. Comandos e a etapa de manifesto estão no arquivo reproducao.json. Os scripts recusam sobrescrever OOF/modelo final ou reabrir o teste. O SHA256 local garante integridade, não é registro externo de pré-registro.\n",
"## Suposições e limites\n",
"Identidade clínica não confirmada; hash/geometria não garantem independência entre pessoas. Tamanho pequeno, especialmente grupo 2. Exclusão de conflitos pode alterar composição dos grupos. Banco global na CV e amostragem condicional ao banco; sensibilidade não remove toda exposição. Câmeras próprias e features reutilizadas, câmeras originais PLACEHOLDER; sem ajuste fino do backbone. Grupos extraídos de rótulos locais, sem adjudicação clínica. Milímetros presumidos para triagem geométrica. Desfechos secundários exploratórios e múltiplos. A avaliação trata consistência/sensibilidade do modelo substituto, sem conclusão sobre Goslon AI nem correção anatômica. Nenhum STL foi produzido ou alterado nesta etapa; arquivos e resultados permaneceram locais, sem push Git.\n"
])
(O/"README.md").write_text("\n".join(parts))
plt.rcParams.update({"font.size":10,"figure.dpi":130,"savefig.dpi":200})
fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True)
for ax,axis in zip(axes,["vertical","anteroposterior","lateral"]):
 for method,color in zip(["nenhuma","centralizado","multi5_rmse"],["#b14a3b","#a57613","#226e99"]):
  rr=sorted([r for r in metrics if r["populacao"]=="sensibilidade_sem_banco" and r["modelo"]=="substituto_canonico" and r["condicao"]=="rotation" and r["normalizacao"]==method and r["eixo"]==axis],key=lambda r:float(r["angulo"]))
  zero=next(r for r in metrics if r["populacao"]=="sensibilidade_sem_banco" and r["modelo"]=="substituto_canonico" and r["condicao"]=="canonical" and r["normalizacao"]==("centralizado" if method=="centralizado" else "referencia_canonica_multi5"))
  rr=[zero]+rr;x=np.array([float(r["angulo"]) for r in rr])
  ax.plot(x,[100*float(r["taxa_troca"]) for r in rr],"o-",label=methods[method],color=color)
  ax.fill_between(x,[100*float(r["taxa_troca_IC95_inf"]) for r in rr],[100*float(r["taxa_troca_IC95_sup"]) for r in rr],alpha=.10,color=color)
 ax.axhline(5,color="gray",linestyle=":",linewidth=.8);ax.axhline(10,color="gray",linestyle="--",linewidth=.8)
 ax.set_title(axis.capitalize());ax.set_xlabel("Rotação conhecida (graus)");ax.set_xticks([0,2,5,10,20]);ax.grid(alpha=.18);ax.set_ylim(0,100)
axes[0].set_ylabel("Troca de predição (%)");axes[-1].legend(fontsize=8,loc="upper left")
fig.suptitle("Modelo substituto — OOF em 41 conteúdos, excluindo cinco templates da pontuação",fontsize=12)
fig.text(.5,.01,"IC95%: bootstrap de paciente proxy; cinco repetições agregadas. Referência comum: canônica multi5. Sem teste.",ha="center",fontsize=8)
fig.tight_layout(rect=[0,.04,1,.93])
for ext in ["png","pdf"]:fig.savefig(R/f"tolerancia_apenas_OOF.{ext}")
plt.close(fig)
rows=read(R/"confusao_teste_final.csv");fig,axes=plt.subplots(1,3,figsize=(10,4.6))
for ax,model in zip(axes,names):
 cm=np.zeros((3,3))
 for r in rows:
  if r["modelo"]==model:cm[int(r["grupo_real"])-1,int(r["predicao"])-1]=float(r["pacientes_proxy_equivalentes"])
 ax.imshow(cm,cmap="Blues",vmin=0,vmax=7)
 for i in range(3):
  for j in range(3):ax.text(j,i,f"{cm[i,j]:g}",ha="center",va="center",color="white" if cm[i,j]>4 else "black")
 ax.set_xticks(range(3),[1,2,3]);ax.set_yticks(range(3),[1,2,3]);ax.set_xlabel("Grupo predito");ax.set_ylabel("Grupo real");ax.set_title(names[model],fontsize=10)
fig.suptitle("Teste final canônico — 16 pacientes proxy (7 / 3 / 6)",fontsize=12)
fig.text(.5,.02,"Modelo substituto; grupo 2 tem menos de cinco pacientes. Reanálise interna, com exposição histórica.",ha="center",fontsize=8)
fig.tight_layout(rect=[0,.13,1,.93])
for ext in ["png","pdf"]:fig.savefig(R/f"confusao_teste_canonico.{ext}")
plt.close(fig)
primary=load(R/"primario_teste.json")
(O/"status.json").write_text(json.dumps({"status":"CONCLUIDO","rotulo":"modelo substituto","elegiveis":62,"desenvolvimento":46,"teste":16,"CV_ajustes":20,"test_scope":"somente canonica","tolerancia":"apenas OOF desenvolvimento","paciente_real_confirmado":False,"templates":"banco global, sensibilidade sem 5 na pontuacao","teste_inedito":False,"resultado_primario":primary,"privacidade":"local, apenas IDs, nenhum envio externo"},ensure_ascii=False,indent=2)+"\n")
print("Relatório e figuras consolidados sem alteração de decisões, previsões ou parâmetros.")
