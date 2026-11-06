from pathlib import Path
import csv,json,collections
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
read=lambda f:list(csv.DictReader((ROOT/f).open()))
summary=json.loads((ROOT/'resultados/robustez_resumo.json').read_text());units=read('unidades.csv');bases=read('bases.csv');manual=read('revisao_manual.csv');templates=json.loads((ROOT/'templates/selecao.json').read_text());pairs=read('pareamento.csv')
baseline=json.loads((ROOT/'resultados/normalizacoes_originais.json').read_text())
rmse_stats={}
for category in ['superior','inferior','indeterminada','registro_mordida']:
 values=np.array([r['RMSE'] for r in baseline if r['categoria']==category])
 rmse_stats[category]={'min':float(values.min()),'mediana':float(np.median(values)),'max':float(values.max())}
(ROOT/'resultados/rmse_por_categoria.json').write_text(json.dumps(rmse_stats,indent=2))
fmt=lambda v:f'{v:.6g}'
table='\n'.join('| '+ ' | '.join([a,str(s['stl']),str(s['ensaios']),fmt(s['media_graus']),fmt(s['desvio_populacional_graus']),fmt(s['max_graus']),f"{100*s['taxa_falha']:.2f}%"] )+' |' for a,s in summary.items())
manualtable='\n'.join(f"| {r['id']} | {r['categoria']} | {r['paciente']} | [PNG]({r['preview']}) | {r['coincidencia_sha256_com_arcada_nomeada'] or '—'} |" for r in manual)
unitflags=[r['id'] for r in units if r['incompativel_mm_heuristica']=='True']
basecount=sum(r['base_detectada_operacional']=='True' for r in bases)
base_arch=sum(r['base_detectada_operacional']=='True' and r['arcada'] in ['superior','inferior'] for r in bases)
base_bite=sum(r['base_detectada_operacional']=='True' and r['arcada']=='registro_mordida' for r in bases)
base_table='\n'.join(f"| {r['id']} | {r['arcada']} | {100*float(r['fracao_triangulos_base_candidata']):.2f}% | {100*float(r['fracao_area_base_candidata']):.2f}% |" for r in bases if r['base_detectada_operacional']=='True')
ranges=[]
for a in ['superior','inferior']:
 rs=[r for r in units if r['arcada']==a]
 values=[(k,[float(r[k]) for r in rs]) for k in ['largura_X_nativa_mm_assumido','profundidade_Y_nativa_mm_assumido','largura_PCA1_mm_assumido','profundidade_PCA2_mm_assumido']]
 ranges.append(a+': '+ '; '.join(f'{k}: {min(v):.2f}–{max(v):.2f}' for k,v in values))
text=f'''# Etapa 1 — pareamento, planos e normalização rígida

Processamento inteiramente local; não houve envio de STL a serviços externos. A instalação de bibliotecas baixou somente dependências. Nenhuma interface ou câmera de treino foi criada.

## Arquivos e integridade

158 STL físicos foram copiados para `copias/`, preservando caminhos e conteúdo; 139 SHA-256 únicos. O ZIP e os STL de `dados/` não foram alterados. `manifesto_copias.json` liga IDs, caminhos e hashes iniciais; `validacao_integridade.json` confirma por SHA-256, depois da execução, que todas as 158 fontes e cópias continuam idênticas. Os templates também são cópias, sem corte, reparo ou reescala.

- `pareamento.csv`: {len(pairs)} pastas de paciente, superiores/inferiores e observações. Campos de arquivos contêm listas JSON para preservar múltiplas alternativas. Pareamento é por pasta, não prova identidade, sessão nem oclusão. Repetições idênticas são apontadas; não se fundem pacientes por semelhança de nome.
- `revisao_manual.csv`: 12 indeterminados e quatro registros de mordida, caminhos dos 16 PNG e campo vazio para decisão humana. Coincidência SHA-256 com arquivo nomeado é evidência de conteúdo idêntico, sem promover automaticamente a classificação.
- `unidades.csv`: bounding box XYZ nativa e bounding box orientada pelos eixos PCA para cada STL.
- `bases.csv`: RANSAC, classificação operacional, fração de triângulos e área, além dos quatro planos candidatos por arquivo.
- `pose_normalize.py`: implementação Open3D; `templates/selecao.json`: templates e critério.
- `resultados/normalizacoes_originais.json`: R, t, RMSE simétrico, RMSE de inliers, fitness e quatro candidatos por STL original.
- `resultados/robustez_ensaios.csv`: 3.160 ensaios, com Q/u aplicados, R/t estimados, erro geodésico, erro de translação, RMSE e indicador de falha.
- `resultados/robustez_por_stl.csv`, `resultados/robustez_resumo.json` e `resultados/histograma_*.png`: métricas por arquivo e por categoria, incluindo resumo adicional sem duplicatas.

## Unidades e dimensões

STL não declara unidade. **mm é uma suposição**, sem conversão automática. Largura X e profundidade Y são extensões no referencial nativo; não se conhece a correspondência anatômica desses eixos. PCA1/PCA2 são extensões geométricas ao longo dos dois primeiros autovetores; não se garante que sejam largura/profundidade anatômicas.

Triagem heurística: maior dimensão PCA >150, PCA1 <15 ou PCA2 <10 unidades. Limiares amplos de engenharia para destacar possíveis fatores 10/1000, não intervalos clínicos validados. Um resultado compatível não comprova mm. Aplicados também aos registros de mordida e indeterminados, que exigem interpretação separada.

Casos sinalizados: {', '.join(unitflags) if unitflags else 'nenhum'}. Valores por arcada (mm assumido):

- {ranges[0]}
- {ranges[1]}

## Bases por RANSAC

Amostra uniforme por área de 12.000 pontos, semente fixa, até quatro planos extraídos sequencialmente, 700 hipóteses por plano e distância de inlier de 0,20 unidades. Um triângulo pertence ao candidato se **todos os seus vértices** estiverem a no máximo 0,25 unidades do plano e sua normal formar até 12° com a normal do plano (sinal ignorado).

Classificação operacional de base provável: maior plano com >=4% da área total e >=100 triângulos. Resultado: **{basecount}/158 arquivos com plano grande**, sendo **{base_arch} arcadas com base candidata** e **{base_bite} registros de mordida com planos grandes**. Nos registros, o status específico não classifica a superfície como base de gesso. A fração de triângulos usa o número total de faces como denominador; a fração de área é reportada à parte para reduzir o efeito da tesselação. A coluna de base candidata vale zero quando não passa no limiar; o melhor plano encontrado continua registrado, inclusive nesses casos.

**Plano grande não identifica material nem anatomia.** Uma superfície palatina/dental pode produzir falso positivo; uma base curva, irregular ou fora dos quatro planos pode gerar falso negativo. Portanto `BASE_PROVAVEL_REVISAR` e `SEM_PLANO_GRANDE_DETECTADO_NAO_EXCLUI_BASE` são evidência geométrica, não verdade clínica. Não houve recorte nem tratamento de base para o ICP. Os limiares são suposições, registrados em `parametros.json`.

| ID | Categoria | Triângulos no plano candidato | Área no plano candidato |
|---|---|---:|---:|
{base_table}

## Templates e normalização

“Orientação mediana” foi operacionalizada como **medoide angular**: arquivo observado que minimiza a soma das distâncias geodésicas entre frames PCA, minimizadas nas quatro combinações próprias de sinais, após deduplicação SHA-256. Seleção usa PCA exata da superfície do inventário inicial. Não existe uma mediana única simples para matrizes de rotação.

Como cada STL contém uma arcada, a escolha de template foi interpretada por categoria: há um template por categoria, evitando alinhar uma superior contra uma inferior. **Suposição:** os templates superior/inferior podem pertencer a pacientes diferentes; os alinhamentos independentes não preservam nem validam a relação oclusal entre arcadas. Não devem ser usados como alinhamento de um par em oclusão. Para esse uso, deve-se escolher um único paciente-template pareado e estimar uma transformação rígida comum ao conjunto superior+inferior. Indeterminados e registros de mordida usam templates próprios apenas para auditoria; o conjunto indeterminado pode misturar anatomias, portanto seus resultados não representam normalização anatômica validada.

'''
for t in templates:text+=f"- **{t['categoria']}**: {t['id']}, `{t['arquivo']}`. Distância angular média ao conjunto (inclui o próprio exemplar): {t['distancia_media_medoid_graus']:.2f}°.\n"
text+='\nRMSE simétrico do baseline por categoria (mínimo / mediana / máximo, unidades supostamente mm):\n\n'
for a,v in rmse_stats.items():text+=f"- {a}: {v['min']:.4f} / {v['mediana']:.4f} / {v['max']:.4f}.\n"
text+='''
O alinhamento amostra 2.048 pontos uniformes por área com semente fixa, centraliza no centroide dessa amostra e recalcula PCA. Não altera escala. Para cada uma das quatro matrizes diagonais com determinante +1, inicializa `R = A_template S A_sourceᵀ`, `t = c_template − R c_source`, e executa ICP point-to-point Open3D (60 iterações máximas, distância máxima 8 unidades, tolerâncias relativas 1e-8).

A solução escolhida minimiza **RMSE simétrico de vizinhos mais próximos, sem corte**, calculado nas duas direções após ICP. Isso evita escolher candidatos só por poucos inliers. O `icp_inlier_rmse` nativo do Open3D e a fração `fitness` também são preservados. RMSE é em unidades nativas, supostamente mm. ICP sempre usa geometria sem reflexão e sem escala.

Convenção de saída: **`x_normalizado = R @ x_original + t`**, com vetores coluna, R 3×3 e t 3. O referencial final é o referencial nativo do template; centralizar é etapa de cálculo e não significa que a saída final tenha centro na origem. O template não estabelece eixos anatômicos canônicos. Centroide amostral pode diferir do centroide exato de superfície da etapa 0.

## Robustez sob variação de pose

Para cada um dos 158 STL, 20 rotações Haar uniformes em SO(3), sem espelhamento, e translações independentes uniformes em [−100,100] por eixo. Cada ensaio chama novamente PCA e os quatro ICP; não reutiliza a rotação estimada no baseline.

Com perturbação `x' = Q x + u`, baseline R₀ e nova normalização R₁, o erro é `acos(clip((trace((R₁ Q) R₀ᵀ)−1)/2,−1,1))`. Assim compara-se o efeito composto no referencial original, sem confundir a perturbação aplicada com erro residual. Falha: erro estritamente >5°. Desvio padrão populacional (`ddof=0`). Erro de translação: norma de `R₁u + t₁ − t₀`.

| Categoria | STL | Ensaios | Média (°) | Desvio (°) | Máximo (°) | Falha >5° |
|---|---:|---:|---:|---:|---:|---:|
'''+table+'''

![Histograma superior](resultados/histograma_superior.png)
![Histograma inferior](resultados/histograma_inferior.png)

**Limites do teste:** as perturbações são aplicadas à mesma amostra de superfície por arquivo, preservando exatamente os pontos e isolando equivariância rígida. Não há reamostragem independente, ruído, malha recortada, retesselação ou serialização de STL perturbado. Recalcula-se PCA da nuvem transformada em cada chamada; não se transforma a resposta conhecida. Nuvens são transformadas em memória, sem escrever novas malhas. Taxas muito baixas demonstram repetibilidade do algoritmo nessas condições, não acurácia anatômica nem equivalência ao treino. O template participar da própria avaliação facilita seu baseline; as métricas por STL permitem excluí-lo. Duplicatas físicas têm peso repetido no resumo principal; resumo deduplicado adicional no JSON. Bases e geometrias simétricas ainda podem levar a uma pose errada, mas repetível.

## Revisão manual — todos os 16 arquivos

Os PNG mostram três ângulos geométricos offline, com eixos nativos, sem enquadramentos de treino. Malha visual reduzida por simplificação quadric Open3D somente para a prévia; RANSAC e medidas usam faces originais/cópias. O caminho completo está em `revisao_manual.csv`.

| ID | Categoria | Pasta de paciente | Preview | SHA idêntico a arcada nomeada |
|---|---|---|---|---|
'''+manualtable+'''

## Reprodução e validação

Ambiente local `.venv/`: Open3D 0.18.0 e NumPy 1.26.4; NumPy 2 provocou falha nativa com esta distribuição do Open3D, resolvida no ambiente isolado. SciPy e Matplotlib são usados para rotações, distâncias e PNG. Dependências registradas em `requirements.txt`.

A partir da raiz do projeto:

```sh
"etapa1/.venv/bin/python" "etapa1/scripts/executar.py" > "etapa1/execucao.log" 2>&1
"etapa1/.venv/bin/python" "etapa1/scripts/atualizar_figuras.py"
"etapa1/.venv/bin/python" "etapa1/scripts/resumir.py"
"etapa1/.venv/bin/python" "etapa1/scripts/verificar.py"
```

Uso individual (caminhos sempre entre aspas):

```sh
"etapa1/.venv/bin/python" "etapa1/pose_normalize.py" "CAMINHO_DA_COPIA.stl" "etapa1/templates/superior.stl" --output "etapa1/resultados/alinhamento_individual.json"
```

`verificar.py` verifica um plano sintético RANSAC com fração conhecida e recuperação de uma transformação conhecida em geometria sintética assimétrica, convenção de composição, ortogonalidade e determinante +1 de todos os candidatos baseline, 20 ensaios por arquivo, 16 PNG e cobertura dos relatórios. Hashes completos são verificados ao final do processamento. Não se instala servidor nem se faz chamada REST.
'''
(ROOT/'README.md').write_text(text)
print('README gerado. Planos grandes:',basecount,'Sinalizados unidade:',unitflags)
