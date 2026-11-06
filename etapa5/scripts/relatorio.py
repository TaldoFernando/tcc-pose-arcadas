from common import *

def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def fmt(r,factor=1):return f"{r['estimate']*factor:.2f} [{r['CI95'][0]*factor:.2f}; {r['CI95'][1]*factor:.2f}]"

def main():
 stats=load('resultados/estratos_bootstrap.json');cor=load('resultados/correlacoes.json');balanced=load('resultados/balanceado_bootstrap.json');dist=csv_read('resultados/estabilidade_diferencas.csv');plans=load('planos/divisoes.json');freeze=load('congelamento.json');globalstats=load('resultados/original_global_bootstrap.json')
 group_rows=[]
 for method,groups in stats.items():
  for group,s in groups.items():group_rows.append([method,group,f"{s['n_IDs']}/{s['failure5']['n_patient_contents']}",fmt(s['median_error_deg']),*[fmt(s['failure'+str(t)],100) for t in [2,3,5,10]]])
 corrrows=[]
 for method,d in cor.items():
  for name in ['goslon_failure5','RMSE_failure5']:
   r=d[name];corrrows.append([method,name,r['n'],f"{r['rho']:.3f}",f"[{r['CI95'][0]:.3f}; {r['CI95'][1]:.3f}]",f"{r['permutation_p_two_sided']:.4f}"])
 choices=csv_read('resultados/templates_por_grupo.csv');choice_rows=[[g]+[f"{100*float(next(r['mean_patient_content_fraction'] for r in choices if r['query_grupo']==str(g) and r['template_ID']==t)):.1f}%" for t in ['P016','P004','P045','P029','P002']] for g in [1,2,3]]
 vert=csv_read('resultados/vertical_por_grupo.csv');vrows=[[r['method'],r['grupo'],*[f"{float(r[k]):.2f}" for k in ['signed_group_mean','SD_between_patient_means','mean_within_patient_SD']],f"{100*float(r['bias_fraction']):.1f}%",r['predominante']] for r in vert]
 drows=[]
 for r in dist:
  if r['metric'] not in ['failure5','median_error_deg']:continue
  m=100 if r['metric']=='failure5' else 1;drows.append([r['comparison'],r['metric'],*[f"{float(r[k])*m:.2f}" for k in ['median','q25','q75','min','max']],r['splits_improved']+'/10'])
 brows=[[g,fmt(balanced[g]['failure5'],100),fmt(balanced[g]['paired_delta_failure5'],100),fmt(balanced[g]['median_RMSE'])] for g in ['1','2','3','overall']]
 splitrows=[[p['name'],p['primary'],', '.join(p['bank'])] for p in plans]
 text=f'''# Etapa 5 — estratificação, templates e estabilidade

Processamento exclusivamente local, em cópias. Relatórios e nomes dos arquivos de saída usam IDs P001…P069. A única correspondência ID→origem está em `privado/id_pasta_local.csv`; não incluir esse arquivo em material para compartilhamento. Não foram enviados dados externamente. Câmeras continuam **PLACEHOLDER**. Nenhuma das seis vistas de treino foi renderizada. O experimento do classificador foi preparado e **não executado**.

## Achados centrais

Nas dez divisões novas, multi5_rmse reduziu a falha >5° em 7/10 comparações com o controle: mediana da diferença −4,44 pontos percentuais, IQR −7,11 a −0,02, faixa −13,18 a +5,27. Portanto o sinal muda em parte das divisões; isso não é garantia de melhora em uma nova população. Em >10° a diferença favoreceu multi5_rmse nas dez divisões, com mediana −4,09 pontos percentuais. As divisões são sobrepostas e a distribuição é descritiva.

O banco balanceado teve falha >5° de 21,70%, contra 23,24% do multi5 original: diferença pareada −1,54 p.p. [IC95% −5,74; +2,45]. O intervalo inclui zero; não há ganho claro demonstrado pelo balanceamento. O erro vertical é predominantemente espalhamento em todos os grupos e métodos originais. GOSLON e RMSE se associam à falha, com as limitações de rótulos, amostra e causalidade detalhadas abaixo.

## Desenho e unidade de análise

Divisão original preservada: 20 IDs no desenvolvimento, 49 no teste; 17 e 47 conteúdos de par distintos, respectivamente. Mesma dupla de SHA256 (superior/inferior) define conteúdo-paciente; isso não prova identidade clínica. P032/P040 e P066/P067 são aliases no teste. Agregamos seus resultados antes da inferência estatística, com peso igual para cada conteúdo. Os 980 ensaios de cada método não são 980 observações independentes.

Cada ID tem 20 ensaios, com rotação própria aleatória e translação conhecida, reamostragem independente, ruído gaussiano de 0,15 na unidade assumida mm, remoção local aleatória de 10–30% e decimação. As mesmas perturbações são usadas entre métodos e divisões; trocar a divisão não cria novas réplicas de ruído. Uma única transformação rígida é aplicada ao par. Rótulos não entram no PCA, frame, ICP, escolha por RMSE ou transformação de uma consulta.

Erro de consistência: `D = R_perturbado @ Q @ R_original.T`; erro angular é a distância geodésica de D à identidade. A referência é a normalização do próprio arquivo original, não uma pose anatômica conhecida. Para multi-template, cada pose é primeiro levada ao frame comum do template primário, inclusive quando o template vencedor muda.

Primeiro calculamos mediana angular, fração acima de cada limiar e mediana de RMSE nos 20 ensaios de cada ID. Aliases recebem média dos resumos individuais. A tabela abaixo apresenta **média das medianas individuais** e média das frações de falha, com IC95% percentil por 10.000 reamostragens de conteúdos-paciente dentro de cada grupo. `mediana_das_medianas_grupo.csv` traz também a mediana entre conteúdos e seu IC95%; `por_ID_grupo.csv` preserva cada mediana individual. Frações nos CSV de ensaios/resumos estão em 0–1; `estratos_IC95.csv` e a tabela abaixo usam porcentagem.

## Rótulos e inconsistências

`rotulos_local.csv`: ID, grupo, goslon, fonte="nome da pasta". Grupo vem do diretório de grupo; GOSLON é extraído literalmente, sem validação clínica e sem correção automática. A auditoria presume a organização grupo 1→GOSLON 1/2, grupo 2→3 e grupo 3→4/5; essa correspondência é uma hipótese de organização dos dados.

- P036: grupo 2, GOSLON 2, incompatível com a correspondência presumida.
- P050: grupo 3, texto de grupo 2, GOSLON 3.
- P021/P039: mesmo conteúdo, grupos 1/2 e GOSLON 2/3 diferentes.
- P066/P067: mesmo conteúdo, grupo 3, GOSLON 4/5 diferentes.

Não alteramos esses rótulos. Conteúdos com GOSLON conflitante são excluídos da tendência principal; conteúdos com grupos conflitantes são excluídos das comparações estratificadas. Na divisão original isso deixa 46 conteúdos para tendência e 47 para os demais resumos. Há sensibilidade removendo todos os IDs sinalizados em `correlacoes.json` (45 conteúdos para tendência). A divergência de rótulo pode refletir cópia indevida, rotulagem ou identidade desconhecida: requer revisão local.

## Estratificação no teste original

Valores: estimativa [IC95%]. Limiar é estritamente `erro > t`.

{table(['Método','Grupo','IDs/conteúdos','Média das medianas (°)','>2° (%)','>3° (%)','>5° (%)','>10° (%)'],group_rows)}

Detalhes: `resultados/por_ID_grupo.csv`, `por_conteudo_grupo.csv`, `estratos_bootstrap.json`, `estratos_IC95.csv`, `mediana_das_medianas_grupo.csv`, `falhas_por_grupo.png`.

## Tendência ordinal e associação com RMSE

Spearman sobre resumos por conteúdo-paciente; falha = fração >5°. Para RMSE usamos a mediana do RMSE simétrico final do template efetivamente escolhido nos ensaios, não o erro de treinamento ou um escore do classificador. IC95% por bootstrap de conteúdos; p bilateral por 10.000 permutações. Análises exploratórias, sem ajuste por múltiplas comparações.

{table(['Método','Associação','n','rho','IC95%','p permutação'],corrrows)}

O GOSLON se associa positivamente à falha nesta amostra, inclusive na análise de sensibilidade. RMSE também se associa à falha, mas isso **não demonstra que o template cause ou explique causalmente o erro**. `correlacoes.json` traz também associações dentro de cada grupo: amostras pequenas e intervalos amplos impedem uma interpretação uniforme, especialmente no grupo 2. Rótulos e geometria podem compartilhar fatores não medidos.

## Templates e teste de balanceamento

Banco original: P016 (grupo 1), P004 (1), P045 (3), P029 (2), P002 (1). Seleção em cada consulta exclusivamente pelo menor RMSE simétrico, sem rótulo da consulta. Proporção média de ensaios por conteúdo-paciente que escolhe cada template:

{table(['Grupo da consulta','P016','P004','P045','P029','P002'],choice_rows)}

`templates_por_grupo.csv` inclui contagens brutas e proporções com peso por conteúdo. P004 não foi escolhido nesses ensaios. Não inferir afinidade clínica da escolha.

Banco balanceado escolhido **apenas nos 20 IDs originais de desenvolvimento**: P016, P004, P045, P029, P033; distribuição 2/2/1 por grupo (cinco vagas não se dividem igualmente por três). Critério congelado: P016 fixo; quotas quase iguais, vagas extras por ordem crescente de grupo; distâncias farthest-first nos seis descritores de extensão das arcadas no frame geométrico, padronizados só com desenvolvimento; sem duplicar conteúdo. Os rótulos foram usados exclusivamente nessa construção offline do banco experimental. A consulta continua escolhendo somente por RMSE, sem receber grupo ou GOSLON.

Comparação do banco balanceado com o banco original, mesmos 49 IDs e perturbações; Δ = balanceado menos original, IC pareado por conteúdo. RMSE em mm presumidos.

{table(['Grupo','Falha >5° balanceado (%)','Δ falha (p.p.) [IC95%]','Mediana RMSE média [IC95%]'],brows)}

Métricas 2/3/5/10°, medianas, correlações e IC estão em `balanceado_bootstrap.json`; escolhas em `templates_balanceados_por_grupo.csv`. Este é um teste de sensibilidade de banco, não uma seleção posterior de novo vencedor. Nenhum parâmetro foi alterado após ver seus resultados.

## Vertical: viés e espalhamento

A componente assinada é o vetor log de SO(3) de `F.T @ D @ F`, expresso em graus, na componente vertical do frame geométrico do template primário. Não são ângulos de Euler independentes. O sinal depende da convenção do frame; perto de 180° o log principal tem descontinuidade de sinal, portanto grandes inversões não devem ser interpretadas como viés anatômico.

Por ID: média assinada μ e desvio populacional σ dos 20 ensaios. Por grupo: média de μ, desvio entre μ individuais, média de σ e decomposição de energia `E[μ²] / (E[μ²]+E[σ²])`, com peso igual por conteúdo. Essa decomposição evita que vieses individuais de sinais opostos se cancelem. É descritiva, com apenas 20 réplicas por ID; não estima viés anatômico verdadeiro nem corrige a variância de estimação de μ.

{table(['Método','Grupo','Média assinada (°)','DP entre médias (°)','Média DP intrapaciente (°)','Fração energia viés','Predomínio'],vrows)}

Em todos os grupos/métodos desta divisão predomina o espalhamento. Isso não elimina vieses individuais. Valores por ID em `por_ID_grupo.csv`; por grupo e energia em `vertical_por_grupo.csv`; gráfico `vertical_por_ID.png` (média ± DP, não IC).

## Estabilidade em dez divisões

Dez seeds 20261110…20261119; 20 IDs de desenvolvimento e 49 de teste em cada uma; conteúdo idêntico nunca atravessa a divisão. Construção por embaralhamento de blocos de conteúdo e preenchimento determinístico até 20 IDs; não é amostragem uniforme sobre todas as partições possíveis. Os métodos são aplicados ao mesmo teste de cada seed. O primário é o medoide das orientações PCA superiores dos conteúdos de desenvolvimento; o banco de cinco é escolhido de novo por farthest-first geométrico, com padronização só no desenvolvimento. Nenhum rótulo participa das dez seleções geométricas.

{table(['Divisão','Primário','Banco de templates'],splitrows)}

Distribuição das diferenças entre métodos nas dez divisões novas. Negativo favorece o primeiro método. Falha em pontos percentuais; medianas em graus. IQR apresentado como Q25/Q75; mínimo/máximo entre divisões. O plano balanceado original não entra nessa distribuição.

{table(['Comparação','Métrica','Mediana Δ','Q25','Q75','Mínimo','Máximo','Melhorou'],drows)}

As divisões se sobrepõem, assim como os conteúdos e as perturbações. Não tratar dez divisões como dez estudos independentes nem transformar a distribuição acima em IC populacional. `diferencas_pareadas_por_divisao.json` fornece IC por bootstrap pareado de conteúdos dentro de cada divisão, sem ignorar essa sobreposição; `repeticoes_resumo.csv` traz as taxas 2/3/5/10°, e `repeticoes_por_ID.csv` os resumos individuais. Cada seed usa uma nova referência geométrica, por isso diferenças refletem composição do desenvolvimento, primário e banco conjuntamente; não isolam um efeito único do banco.

## Congelamento, verificações e reprodução

Congelamento UTC: **{freeze['utc']}**, antes da inferência dos novos bancos/divisões. `congelamento.json` contém hashes do protocolo, planos, alinhamentos, código do normalizador e nuvens dos templates. `planos/divisoes.json` registra todos os IDs e transformações; `protocolo.json` declara critérios antes da avaliação. A análise original reaproveita resultados já existentes das etapas anteriores; ela não é um teste prospectivo inédito. Novos resultados são congelados prospectivamente nesta etapa, sobre o mesmo conjunto já estudado.

`resultados/verificacoes.json` registra integridade de 138 cópias e fontes, hashes congelados, ausência de conteúdo compartilhado entre desenvolvimento/teste, templates apenas de desenvolvimento, poses finitas próprias e auditoria local de strings identificáveis. `equivalencia_referencia_original.json` confere a reprodução dos ensaios arquivados de controle/anatômica. `equivalencia_cache.json` compara ajustes diretos com o reuso de poses em frame nativo: conversão rígida para o primário preserva RMSE, evitando repetir o mesmo ajuste entre divisões. `integridade.csv` contém só IDs e flags de SHA256. `execucao_cpu.json` registra a retomada operacional com 12 processos em vez de quatro; somente o paralelismo mudou, usando as mesmas funções e hashes congelados.

Ordem de reprodução, a partir desta pasta e do ambiente Python local já disponível: `scripts/preparar.py`, `planejar.py`, `congelar_planos.py`, `cache_poses.py`, `extrair_referencia.py`, `analise_original.py`, `tabelas.py`, `resumir_cache.py`, `analise_repeticoes.py`, `validar_equivalencia.py`, `relatorio.py`, `verificar.py`. Os três primeiros refazem o preparo/congelamento: **não os executar para apenas consultar os resultados congelados**. Para auditar o congelamento existente, usar `verificar.py`. Scripts de preparo podem abrir fontes históricas identificáveis localmente, mas só a tabela privada conserva essas strings nas saídas desta etapa.

## Experimento futuro do classificador — somente preparado

`experimento_tolerancia_classificador.py` contém `render_views(mesh, camera)` e `predict(images)` como stubs. Aplica a mesma rotação conhecida às duas arcadas, em cópias, separadamente nos eixos látero-lateral, AP e vertical, nos ângulos 0, 2, 3, 5, 10 e 20°. O chamador deve fornecer base canônica coerente com as coordenadas de entrada, um normalizador rígido do par, câmeras verificadas e adaptadores locais. Há bloqueio para PLACEHOLDER e falta de confirmação explícita dos adaptadores.

Compara as predições com/sem normalização e com a referência de 0° de cada ramo, além da referência original comum. Mudança de predição mede tolerância/consistência; acurácia clínica exige rótulos validados e plano de avaliação próprio. O script não foi importado/executado como experimento; somente sintaxe/AST verificados. Nenhuma imagem ou predição foi produzida.

## Limites assumidos

Os pares são tratados como articulados conforme a triagem geométrica anterior; isso não certifica oclusão. O vetor entre centroides orienta o sinal vertical do PCA; a largura relativa das extremidades do arco inferior presume a abertura posterior do U. Bases, falhas de superfície e fissuras podem contrariar essas hipóteses. ICP usa geometria, sem certificação anatômica. Unidades continuam assumidas em mm a partir da escala dos dados. Métricas medem **consistência**, nunca correção anatômica. Rótulos não foram usados para adaptar normalizações por grupo. trim_20, posterior_60 e porta de qualidade foram descartados nesta etapa, sem novos cálculos ou ajustes sobre eles.
'''
 (OUT/'README.md').write_text(text)
 print('README CONCLUIDO: apenas IDs e resultados locais')
if __name__=='__main__':main()
