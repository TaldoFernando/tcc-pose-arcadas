from common import *
from avaliar import stats

def main():
    split=load_json('divisao.json');rule=load_json('regra.json');gate=load_json('porta_qualidade.json');frozen=load_json('congelamento.json');summary=load_json('resultados/resumo.json');auc=load_json('resultados/ROC_AUC.json');causes=load_json('resultados/causas_etapa2.json');devrules=load_json('desenvolvimento/comparacao_regras.json')
    old=list(csv.DictReader((OUT/'referencia_etapa2/ensaios.csv').open()));globalold={m:stats([float(r['erro_angular_graus']) for r in old if r['metodo']==m]) for m in ['superior','combinada']}
    save_json('resultados/etapa2_global.json',globalold)
    rows=[]
    for subset in ['dev','test']:
        for method,v in summary[subset].items():
            if method=='porta':continue
            rows.append(f"| {subset} | {method} | {v['n']} | {v['media']:.3f} | {v['desvio_populacional']:.3f} | {v['mediana']:.3f} | {v['q1']:.3f}–{v['q3']:.3f} | {v['IQR']:.3f} | {v['max']:.3f} | {100*v['taxa_falha']:.2f}% | {v['inversoes_maior90']} |")
    oldtable='\n'.join(f"| {m} | {v['media']:.3f} | {v['mediana']:.3f} | {v['q1']:.3f}–{v['q3']:.3f} | {v['IQR']:.3f} | {v['menor5']} | {v['moderado_5a90']} | {v['inversoes_maior90']} |" for m,v in globalold.items())
    causetable='\n'.join(f'| {s} | {m} | {cause} | {n} |' for s,data in causes.items() for m,counts in data.items() for cause,n in counts.items())
    rule_table='\n'.join(f"| {v['vertical_mode']} | {v['weight']} | {100*v['falhas_maior90']:.2f}% | {v['mediana_erro_inicial']:.3f}° |" for v in devrules)
    auctable='\n'.join(f"| {s} | {m} | {v['AUC']:.3f} |" for s,data in auc.items() for m,v in data.items())
    gatetable='\n'.join(f"| {s} | {v['n']} | {v['rejeitados']} | {v['falhas_rejeitadas']} | {v['sucessos_rejeitados']} | {v['falhas_escaparam']} | {v['aceitos']} | {100*v['taxa_falha_entre_aceitos']:.2f}% |" for s in ['dev','test'] for v in [summary[s]['porta']])
    basereview=list(csv.DictReader((OUT/'resultados/porta_baselines.csv').open()));baseline_counts={s:sum(r['subset']==s and r['revisar_manualmente']=='True' for r in basereview) for s in ['dev','test']}
    worst=list(csv.DictReader((OUT/'revisao/piores10_teste.csv').open()));worsttable='\n'.join(f"| {r['rank']} | {r['id']} | {r['ensaio']} | {float(r['erro_graus']):.3f}° | {r['revisar_manualmente']} | [PNG]({r['PNG']}) |" for r in worst)
    text=f'''# Etapa 3 — sinais orientados por hipóteses anatômicas e porta de qualidade

Processamento somente em cópias locais, sem envio externo. As seis câmeras continuam **PLACEHOLDER**, sem geração das seis vistas de treino. Não há landmarks manuais nem alegação de correção anatômica. As métricas abaixo medem **consistência em relação ao baseline do próprio par**.

**Resultado principal no teste:** a regra nova eliminou inversões >90° observadas no controle PCA (0 contra 11), mas ambos tiveram taxa de falha >5° de {100*summary["test"]["anatomica"]["taxa_falha"]:.2f}%. A média diminuiu e a mediana ficou semelhante. A melhora da cauda extrema não equivale a resolver a instabilidade moderada nem a provar anatomia correta. A porta rejeita muitos casos para capturar a maior parte das falhas.

## 0. Como foi medida a dispersão da Etapa 2

Foi usado o frame completo dos **três autovetores PCA da superfície superior**, e não um único eixo. Para cada paciente, `A_i` contém os eixos como colunas; depois da normalização, `B_i = R_i @ A_i`. Entre todos os pares de pacientes i,j, calculou-se o menor ângulo geodésico de `B_i.T @ B_j @ S`, onde S percorre as quatro diagonais de sinais com determinante +1. Não é distância de um eixo ao template.

O ICP ajusta superfícies de formas diferentes e não impõe coincidência dos eixos PCA após o refinamento. Além disso, a PCA do inventário era exata e ponderada por área, enquanto a inicialização do ICP usava amostras. Refinamento, diferenças de forma, bases e amostragem deixam dispersão residual. Se a saída fosse apenas o alinhamento exato dos mesmos frames PCA, sem esses efeitos, a dispersão desse frame poderia ser artificialmente zero.

## 1. Divisão e prevenção de ajuste pelo teste

`divisao.json`: seed **20261106**, 20 pares físicos para desenvolvimento e 49 para teste. Grupos de conteúdo idêntico por SHA-256 do par foram embaralhados e selecionados por subset-sum determinístico até 20; nenhum STL idêntico, nem de uma só arcada, cruza a divisão.

- Desenvolvimento: {', '.join(split['desenvolvimento'])}.
- Teste: {', '.join(split['teste'])}.

As seis alternativas de regras foram comparadas somente no desenvolvimento. O template **{rule['template_id']}** foi selecionado como medoide PCA superior somente entre pares únicos do desenvolvimento. Não se usou o template P063 da Etapa 2 como referência do novo algoritmo, pois ele está no conjunto de teste.

Congelamento em **{frozen['utc']}**: `congelamento.json` guarda hashes de regras, código de inferência, replay, divisão, template e porta de qualidade, antes de avaliar o teste. `verificar.py` confirma que esses arquivos não mudaram. O teste foi avaliado uma vez com esses parâmetros; gráficos, seleção dos piores e relatório foram produzidos depois, sem retroalimentar a regra ou o limiar.

**Limite:** os mesmos dados já tinham sido analisados de forma agregada na Etapa 2. Este é um holdout interno com congelamento prospectivo das regras da Etapa 3, não uma validação externa inédita nem separação clínica por identidade confirmada. Duplicatas ficam juntas, mas pastas não provam identidades independentes.

## 2. Diagnóstico das falhas da Etapa 2

`resultados/diagnostico_falhas_etapa2.csv` contém **todas as 1.104 falhas** dos dois métodos da Etapa 2, reexecutadas com exatamente as mesmas amostras, ruído, recortes, decimações, Q e u. A rotação escolhida foi conferida contra o CSV antigo. Para cada falha, são registrados:

- índice e sinais do candidato escolhido entre as quatro matrizes próprias `diag(−1,−1,+1)`, `diag(−1,+1,−1)`, `diag(+1,−1,−1)`, `diag(+1,+1,+1)`;
- candidato inicial mais próximo da transformação-oráculo conhecida; quatro erros iniciais e finais e os quatro RMSE;
- quais candidatos finais teriam erro <=5°, ou **NENHUM**; menor erro entre os quatro, mesmo quando nenhum atende ao critério;
- resultado de um quinto ICP inicializado exatamente na transformação-oráculo de consistência.

O oráculo é `R_esperado = R_baseline @ Q.T`, `t_esperado = t_baseline − R_esperado @ u`. **“Correto” aqui não significa anatomicamente correto:** é a solução consistente com o próprio baseline e a perturbação conhecida. O índice inicial mais próximo nem sempre fornece uma solução final <=5°, e pode nem existir candidato correto entre os quatro quando há mudança de eixos por PCA ou grande desvio do objetivo.

Classificação operacional (não prova causal absoluta):

1. `SELECAO_RMSE_OUTRO_CANDIDATO_CONSISTENTE`: pelo menos outro candidato chegou a <=5°, mas o RMSE fez vencer uma solução inconsistente. É falha de seleção/ranking entre candidatos; não se deve culpar apenas o cálculo dos autovetores.
2. `PCA_GROSSEIRA_E_BACIA_ICP`: nenhum dos quatro funcionou; o ICP no oráculo funciona, mas até o melhor início PCA estava >30° do esperado. Sugere inicialização grosseira, não apenas sinal.
3. `BACIA_LOCAL_ICP`: nenhum candidato funcionou, havia início PCA a <=30° e o ICP no oráculo funciona. É evidência de sensibilidade à bacia de convergência.
4. `DESVIO_MESMO_INICIALIZANDO_NO_ORACULO`: até o ICP iniciado no oráculo termina >5° distante. Recorte/ruído/amostragem mudam o ótimo do objetivo de superfície; não é válido atribuir automaticamente esse caso a sinal errado ou mínimo local. O teste não certifica um mínimo global.

| Conjunto | Referência Etapa 2 | Diagnóstico operacional | Falhas |
|---|---|---|---:|
{causetable}

### Distribuições antigas, incluindo mediana e IQR

| Referência antiga | Média ° | Mediana ° | Q1–Q3 ° | IQR ° | <5° | 5–90° | >90° |
|---|---:|---:|---:|---:|---:|---:|---:|
{oldtable}

Há histogramas por método e conjunto em `resultados/hist_log_*.png`. O eixo do erro é **logarítmico**, com cores separando <5°, 5–90° e >90°. Valores zero seriam truncados em 1e-4° só no gráfico. A falha operacional é estritamente >5°; a classe gráfica moderada inclui o limite exato 5°.

## 3. Regras de orientação, sem landmarks manuais

Implementação: `anatomical_pair.py`, função `normalize_anatomical()`. Recebe nuvens superior e inferior articuladas, mantém uma única transformação própria R/t aplicada às duas.

### Vertical

O vetor entre centroides inferior→superior define o **sinal de para cima**. Compararam-se duas opções só no desenvolvimento: usar o vetor diretamente como eixo (`centroid`) ou orientar por ele o sinal do menor eixo PCA da nuvem combinada (`pca_sign`). Foi escolhida **{rule['vertical_mode']}**. Isso não equivale a dizer que o eixo PCA seja uma vertical anatômica correta; o vetor pode inclinar com recortes e o menor autovalor pode trocar de eixo em casos degenerados.

### Anteroposterior pela abertura do U

Usa-se a **arcada inferior** para estimar a abertura, evitando depender diretamente da fissura superior. Projetam-se seus pontos no plano perpendicular à vertical estimada. A PCA horizontal dá uma direção lateral sem sinal; uma direção AP sem sinal é obtida por produto vetorial.

O cue de abertura compara o afastamento lateral médio `|x|` nos 20% extremos de cada lado de y: supõe-se que o lado posterior aberto tenha dois braços mais afastados da linha média, enquanto o lado anterior forme a ponte do U. O lado de maior afastamento recebe o sentido posterior. Alternativamente, foi testado o deslocamento entre centroide e centro da bounding box por quantis 2–98%, **no frame local**, não na bbox global dependente da pose.

Peso escolhido **{rule['weight']}** para o cue de abertura, com peso `1−peso` para o cue centroide/bbox. Não houve ajuste olhando o teste. Casts com base, arco pouco definido, assimetria, segmento ausente ou recorte de um braço podem violar essa hipótese. Não é detecção anatômica validada de anterior/posterior.

### Lateral e refinamento

Fecha-se o frame com produtos vetoriais: `lateral = posterior × up`, seguido de reortogonalização. O determinante é +1; nunca se usa espelhamento. “Lateral” é um eixo geométrico; sem referência externa, não se certifica direita/esquerda clínica.

O frame orientado inicializa o ICP point-to-point. São usados quatro inícios **próximos**, com 0°, +10°/−10° em torno da vertical local e +10° de inclinação lateral. Não se reintroduzem quatro alternativas de inversão de 180° depois de resolver o sinal. O melhor resultado minimiza RMSE simétrico completo. A discordância é o maior ângulo geodésico entre as quatro soluções finais.

O ICP é o mesmo básico da Etapa 2: distância máxima 8 unidades, 60 iterações, sem escala. A porta usa seu RMSE de inliers; o RMSE simétrico e o fitness também são preservados. O método não restringe a resposta pelo Q conhecido nem usa o erro verdadeiro para selecionar candidatos.

### Seleção no desenvolvimento

Critério: menor taxa de inversões >90° do **frame inicial** nos 400 ensaios de desenvolvimento; desempate pela mediana angular inicial. Não houve busca de parâmetros ICP nem de limiares no teste.

| Vertical | Peso abertura U | Inversões iniciais dev | Mediana erro inicial |
|---|---:|---:|---:|
{rule_table}

## 4. Comparação com as mesmas perturbações

Preservaram-se exatamente as Q/u, seeds, geometria decimada, novas amostras, ruído gaussiano sigma 0,15 e recortes espaciais independentes de 10–30% da Etapa 2: 20 ensaios por par e método. `scripts/replay.py` reproduz os sorteios. Não se adicionaram imagens ou landmarks.

Três referências de comparação:

- `etapa2_combinada`: resultado histórico solicitado, com template P063 escolhido anteriormente entre todos os dados. Mudanças de template impedem atribuir toda a diferença só à regra.
- `pca_controle`: o algoritmo PCA+4 sinais+ICP antigo, **reexecutado com o template de desenvolvimento {rule['template_id']}**, nas mesmas nuvens que o método novo. Isola melhor o efeito da regra/novos inícios.
- `anatomica`: nova regra geométrica com hipótese anatômica. O nome da função não é afirmação de correção anatômica.

`etapa2_superior` é incluído para completar o diagnóstico histórico. Todas as métricas comparam cada método ao seu próprio baseline. Um baseline errado, mas repetível, pode ter baixo erro. Para interpretar correção anatômica seria preciso outro padrão de referência.

| Conjunto | Método | N | Média ° | Desvio ° | Mediana ° | Q1–Q3 ° | IQR ° | Máximo ° | Falha >5° | >90° |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Os ensaios novos completos, inclusive os quatro candidatos por execução, estão em `desenvolvimento/ensaios.json` e `teste/ensaios.json`; baselines em seus respectivos `baselines.json`. Q/u, transformações estimadas e métricas podem ser auditadas individualmente. Os ensaios dentro de cada par são correlacionados; não são 980 pacientes independentes no teste.

## 5. Porta de qualidade congelada

Rótulo de falha: erro de consistência >5° do novo método, não diagnóstico clínico. Foram avaliados RMSE final de inliers, RMSE simétrico e discordância entre candidatos. Discordância baixa não garante sucesso: quatro inícios próximos podem convergir juntos a uma resposta inconsistente ou compartilhar um sinal errado do frame.

| Conjunto | Sinal | ROC AUC |
|---|---|---:|
{auctable}

A porta combina **RMSE de inliers + discordância máxima** com regressão logística padronizada, C=1, classes balanceadas. AUC da porta no desenvolvimento é calculada em predições **out-of-fold**, GroupKFold=5 agrupado por conteúdo do par. Os sinais isolados não foram treinados; suas AUC no dev são descritivas. No teste, todos os sinais e a porta são avaliados sem recalibração.

**Limiar proposto e congelado: revisar manualmente se `score >= {gate['threshold']:.8f}`.** Esse score é a sigmoide do modelo, não probabilidade calibrada. O limiar foi escolhido nas predições OOF para atingir pelo menos 90% de sensibilidade de detecção de falhas no desenvolvimento, com menor taxa de sucessos rejeitados entre os limiares elegíveis. Parâmetros completos em `porta_qualidade.json`.

| Conjunto | Normalizações | Rejeitadas | Falhas rejeitadas | Sucessos rejeitados | Falhas escaparam | Aceitas | Falha nas aceitas |
|---|---:|---:|---:|---:|---:|---:|---:|
{gatetable}

Esses números são **execuções perturbadas**, não pacientes. Pacientes do teste com ao menos uma rejeição em 20 ensaios: {summary['test']['porta']['pares_com_alguma_rejeicao']}/49. No baseline dos pares completos, o limiar sinaliza {baseline_counts['dev']}/20 no desenvolvimento e {baseline_counts['test']}/49 no teste; **não há verdade anatômica para contar falhas escapadas desses baselines**.

`resultados/porta_decisoes.csv` contém todas as rejeições/aceitações dos ensaios, incluindo falhas que escaparam. `porta_baselines.csv` contém o resultado por par original. ROC e AUC medem discriminação de consistência sob este protocolo, sem garantia de validade clínica ou transferência para outros scanners, unidades ou populações.

![ROC teste](resultados/ROC_test.png)

## 6. Revisão dos dez piores casos do teste

Seleção exclusivamente após o congelamento: maior erro do novo método entre os 20 ensaios de cada par, ordenando e evitando repetir conteúdo idêntico. Só foram usados IDs dos 49 pares de teste. A seleção não altera algoritmo nem limiar.

`revisao/contato_10.png` reúne os 10; `folha_01.png` e `folha_02.png` têm cinco cada. Cada PNG individual traz frontal, lateral e oclusal **geométricas**, superior azul e inferior laranja, com erro e decisão da porta.

**O que está desenhado:** as duas malhas completas decimadas, na pose composta estimada do pior ensaio (`R_est @ Q`, `R_est @ u + t_est`). A estimativa veio das nuvens ruidosas/recortadas, mas as malhas exibidas não fingem ter o mesmo recorte/ruído. Isso mostra a inconsistência de orientação sem esconder partes da anatomia; Q/u e os dados perturbados são reproduzíveis no JSON. A relação entre as arcadas continua preservada pela transformação comum.

| Ordem | ID teste | Ensaio | Erro | Porta rejeitou | Preview |
|---|---|---:|---:|---|---|
{worsttable}

## Suposições e limites

- Unidade mm continua assumida. Sigma 0,15, distância ICP 8, recorte 10–30%, limite 5°, pesos do cue e meta de sensibilidade são parâmetros de engenharia, não limites clínicos validados.
- O par já deve estar articulado. A Etapa 2 mostrou compatibilidade geométrica, não certificou oclusão. Centroide inferior→superior só orienta um sinal sob essa hipótese.
- Menor eixo PCA pode mudar com cortes ou base; braços do U podem não estar presentes. Não há anotação de posterior, vertical ou lateral de referência.
- O novo método e o controle não usam Q/u na inferência; Q/u entram apenas em desenvolvimento sintético, avaliação e diagnóstico do oráculo.
- A comparação histórica usa template diferente; o controle PCA com template só do desenvolvimento é a comparação mais controlada.
- O diagnóstico de “mínimo local” é operacional e condicionado ao teste do oráculo. Mudança do objetivo com dados parciais não deve ser confundida com erro puro de sinal.
- A porta tem falsos positivos e falsos negativos, quantificados acima. Aprovação não equivale a orientação anatômica correta.
- O conjunto de teste é interno e já pertence ao estudo anterior; confirmação de identidade clínica, novos casos e referência anatômica continuam necessários para inferências clínicas.
- Nenhuma das seis vistas de treino foi produzida; nenhuma câmera PLACEHOLDER foi substituída.

## Reprodução e verificações

Ambiente local reutilizado: `etapa1/.venv`, NumPy 1.26.4, Open3D 0.18.0, SciPy, Matplotlib e scikit-learn já instalados. Sem chamadas REST ou downloads neste trabalho. `manifesto_copias.json` e `integridade.json` registram 138 STL copiados, fontes e hashes.

Sequência usada (não recalibrar após avaliar teste):

```sh
"etapa1/.venv/bin/python" "etapa3/scripts/copiar.py"
"etapa1/.venv/bin/python" "etapa3/scripts/desenvolver.py"
"etapa1/.venv/bin/python" "etapa3/scripts/executar.py" dev
"etapa1/.venv/bin/python" "etapa3/scripts/calibrar.py"
"etapa1/.venv/bin/python" "etapa3/scripts/executar.py" test
"etapa1/.venv/bin/python" "etapa3/scripts/diagnosticar.py"
"etapa1/.venv/bin/python" "etapa3/scripts/avaliar.py"
"etapa1/.venv/bin/python" "etapa3/scripts/figuras.py"
"etapa1/.venv/bin/python" "etapa3/scripts/verificar.py"
"etapa1/.venv/bin/python" "etapa3/scripts/resumir.py"
```

A divisão foi criada e salva antes do desenvolvimento; para nova pesquisa, use outra pasta/seed e registre novo congelamento. Não sobrescreva este congelamento para alegar teste intocado. `verificar.py` confere divisão sem vazamento de conteúdo, hashes congelados, Q/u idênticos, determinantes +1 e ortogonalidade, equivariância do frame sem perturbações, cobertura das 1.104 falhas, origem dos dez piores e integridade dos STL. Essas verificações de implementação não tornam o alinhamento anatomicamente correto.
'''
    (OUT/'README.md').write_text(text)
    print('README Etapa 3 gerado.')
if __name__=='__main__':main()
