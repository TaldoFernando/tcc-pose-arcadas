from common import *

def ci(v,scale=1):return f"{scale*v['estimate']:.2f} [{scale*v['CI95'][0]:.2f}; {scale*v['CI95'][1]:.2f}]"

def main():
    split=load_json('divisao.json');choices=load_json('escolhas.json');selected=choices['selected'];frozen=load_json('congelamento.json');summ=load_json('resultados/bootstrap_resumo.json');axes=load_json('resultados/eixos_resumo.json');oracle=load_json('resultados/oraculos292_resumo.json');concentration=load_json('resultados/concentracao_falhas.json');contrasts=load_json('resultados/bootstrap_contrastes.json');templates=load_json('templates/selecao.json')
    methods=['pca_controle','anatomica']+selected
    ci_rows=[];rate_rows=[];axis_rows=[];contrast_rows=[];con_rows=[]
    for subset in ['dev','test']:
        for method in methods:
            data=summ[subset][method];nom=data['nominal_IDs'];cluster=data['content_cluster_bootstrap']
            ci_rows.append(f"| {subset} | {method} | {ci(nom['mean_patient_median'])} | {ci(nom['failure_rate_5deg'],100)} | {ci(cluster['mean_patient_median'])} | {ci(cluster['failure_rate_5deg'],100)} |")
            rate_rows.append(f"| {subset} | {method} | "+' | '.join(ci(cluster[f'failure_rate_{t}deg'],100) for t in [2,3,5,10])+' |')
            a=axes[subset][method];shares=a['content_balanced_energy_share'];med=a['mean_patient_abs_median_deg']
            axis_rows.append(f"| {subset} | {method} | {med['lateral']:.2f} / {med['AP']:.2f} / {med['vertical']:.2f} | {100*shares['lateral']:.1f}% / {100*shares['AP']:.1f}% / {100*shares['vertical']:.1f}% | {a['patient_dominant_counts']} |")
            c=concentration[subset][method]
            con_rows.append(f"| {subset} | {method} | {c['failures']} | {c['patients_any_failure']} | {c['patients_for50pct']} | {c['patients_for80pct']} | {100*c['top5_failure_share']:.1f}% | {100*c['top10_failure_share']:.1f}% |")
            if method!='pca_controle':
                v=contrasts[subset][method];contrast_rows.append(f"| {subset} | {method} | {ci(v['delta_mean_patient_median'])} | {ci(v['delta_failure_rate5'],100)} |")
    devtable='\n'.join(f"| {m} | {100*v['mean_patient_failure5_content_balanced']:.2f}% | {v['mean_patient_median_content_balanced']:.2f}° | {'sim' if m in selected else 'não'} |" for m,v in choices['all_metrics_dev'].items())
    dominant_text=[]
    for method in methods:
        a=axes['test'][method];energy=a['content_balanced_energy_share'];dominant=max(energy,key=energy.get);dominant_text.append(f"- **{method}**: maior fração de energia no eixo **{dominant}** ({100*energy[dominant]:.1f}%), com pesos iguais entre conteúdos-paciente.")
    text=f'''# Etapa 4 — medidas repetidas, eixos e variantes de refinamento

Somente cópias locais, sem envio externo. Mesma divisão **20/49** da Etapa 3. Câmeras de treino preservadas como **PLACEHOLDER**; nenhuma das seis vistas foi gerada. Não se afirma correção anatômica. Toda medida de erro é de consistência em relação à normalização do par original pelo mesmo método.

## Unidade de análise e arquivos por paciente

Os 980 ensaios do teste são **49 pares ×20 repetições**, não 980 pacientes. `resultados/por_paciente.csv` registra para cada ID/método/conjunto: mediana, média, máximo, número de falhas >5° e porcentagens >2°, >3°, >5°, >10°. Não se calcula IC binomial fingindo independência entre os 20 ensaios.

Há duplicatas de conteúdo: desenvolvimento 20 IDs, **17 conteúdos únicos**; teste 49 IDs, **47 conteúdos únicos**. No teste, P032/P040 e P066/P067 são aliases por SHA-256 das duas arcadas. Não se confirma identidade clínica por pasta ou hash; conteúdo idêntico também não pode ser contado como informação independente.

Reportamos dois estimandos explicitamente:

1. **Nominal, solicitado:** média das medianas individuais e média das taxas de falha dos 20/49 IDs. Bootstrap reamostra IDs inteiros com todas as repetições.
2. **Conservador por conteúdo-paciente:** primeiro calcula as mesmas medidas por ID, depois tira a média dentro de cada grupo de conteúdo idêntico; cada um dos 17/47 grupos recebe peso igual. Bootstrap reamostra esses grupos inteiros. Além de corrigir a unidade de reamostragem, isso reduz o peso extra das cópias; por isso o ponto estimado pode mudar um pouco.

Seed **20261107**, 10.000 reamostragens, IC percentil de 95%, separadamente em desenvolvimento/teste. Os métodos compartilham os mesmos sorteios; contrastes são pareados por paciente/grupo. `bootstrap_resumo.json` também traz a mediana das medianas individuais com seu IC. Não se reamostram ensaios isolados. Intervalos são exploratórios/pontuais, sem ajuste para múltiplas comparações e sem representar validação clínica externa.

| Conjunto | Método | Média de medianas °: IDs [IC95] | Falha >5° (%): IDs [IC95] | Média de medianas °: conteúdo [IC95] | Falha >5° (%): conteúdo [IC95] |
|---|---|---:|---:|---:|---:|
{chr(10).join(ci_rows)}

`bootstrap_contrastes.json`: diferenças pareadas **variante − controle**. Valor negativo favorece menor erro/menor falha; um IC que inclui zero não estabelece diferença neste protocolo. `bootstrap_contrastes_regra.json` repete os contrastes contra a regra orientada (`anatomica`), para comparar refinamentos com a mesma família de inicialização.

| Conjunto | Método − controle PCA | Δ média das medianas ° [IC95] | Δ falha >5, pontos percentuais [IC95] |
|---|---|---:|---:|
{chr(10).join(contrast_rows)}

![IC por paciente](resultados/IC_pacientes_test.png)

## Quantos pacientes concentram as falhas?

A tabela mantém os IDs físicos pedidos. “Para 50%/80%” é o menor número de pacientes, ordenados por número de falhas, necessário para alcançar aquela fração das falhas. Cada ID tem 20 ensaios. O ranking completo, inclusive os IDs com zero falhas, está em `concentracao_falhas.json`. Aliases são identificados acima; estes números descritivos não dão independência a eles.

| Conjunto | Método | Falhas | Pacientes com alguma falha | Pacientes para 50% | Para 80% | Fração nos top 5 | Nos top 10 |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(con_rows)}

## Decomposição do erro de rotação

Para cada ensaio: `D = R_estimado @ Q @ R_baseline.T`. Usou-se o **logaritmo de SO(3)**, `v = log(F.T @ D @ F)` em graus. F contém colunas [látero-lateral, AP, vertical], estimadas pela regra geométrica da Etapa 3 no template primário P016. A norma `||v||` recupera o erro geodésico. São componentes de um vetor de rotação resultante, **não três rotações Euler sequenciais**; não há ordem arbitrária nem gimbal lock. Perto de 180°, o sinal do eixo pode ser ambíguo, então os resumos usam magnitudes e quadrados.

“Vertical/AP/lateral” são rótulos geométricos sob as hipóteses de centroides do par, menor eixo PCA e abertura do U. Não se certifica vertical clínica, plano oclusal, direita/esquerda ou direção anatômica real.

Duas medidas complementares:

- por paciente, mediana do valor absoluto de cada componente, depois média dessas medianas;
- fração `v_eixo² / ||v||²` por ensaio, média dentro de cada paciente e dentro dos aliases, depois média com peso igual entre conteúdos-paciente. Essa fração soma 100% e evita que uma única rotação enorme domine a soma de quadrados global.

A contagem de eixo dominante por ID usa a maior mediana absoluta daquele paciente. O eixo pode mudar conforme o critério; ambos são expostos em vez de selecionar a medida mais favorável.

| Conjunto | Método | Média das medianas absolutas LL / AP / V (°) | Fração de energia LL / AP / V | IDs por eixo dominante |
|---|---|---|---|---|
{chr(10).join(axis_rows)}

No teste, pela fração de energia com pesos iguais:

{chr(10).join(dominant_text)}

![Eixos no teste](resultados/eixos_test.png)

Todos os componentes assinados estão em `componentes_rotacao.csv`. A soma quadrática foi verificada contra o erro total.

### Os 292 casos que se afastaram começando na transformação conhecida

Foram **reexecutados**, recuperando R final (o CSV anterior guardava apenas erro escalar), e o erro escalar foi conferido contra a Etapa 3. Para esse estudo histórico, usa-se o frame geométrico do **template antigo P063**, pois as transformações desses oráculos estão naquele referencial; não se aplica diretamente o frame P016 a matrizes expressas em outro referencial.

- Casos: {oracle['n_cases']}; IDs de pacientes envolvidos: {oracle['n_patient_ids']}; conteúdos únicos: {oracle['n_unique_contents']}.
- Eixo com maior componente por caso: **{oracle['dominant_axis_case_counts']}**.
- Fração de energia com pesos iguais por conteúdo-paciente: **{ {k:round(100*v,1) for k,v in oracle['content_balanced_energy_share'].items()} }%**.

`oraculos292_componentes.csv` contém cada componente e `oraculos292_resumo.json` o número de casos por paciente. São dois métodos históricos e repetições dos mesmos pacientes, não 292 observações independentes. A análise é condicionada ao fato de já terem falhado; dominância de eixo não prova uma causa anatômica nem permite generalizar para todas as execuções.

## Variantes e escolha somente no desenvolvimento

As configurações foram declaradas antes do teste em `plano_preteste.json`. Usaram-se as mesmas Q/u, amostras independentes, sigma 0,15, recortes de 10–30% e geometrias decimadas das etapas anteriores, via replay. Não há ajuste de unidade/escala. Todos os métodos aplicam **um único R/t às duas arcadas**.

Inicialização comum: regra orientada da Etapa 3 e os mesmos quatro inícios próximos (0, ±10° na vertical local e +10° lateral). Máximo 60 iterações e distância máxima 8 unidades, assumidas mm. O controle PCA e a regra nova originais são os resultados arquivados da Etapa 3, sem recalcular ou selecionar seus ensaios. Um teste verifica que o caminho ponto-a-ponto de referência reproduz a regra anterior.

### (a) Ponto-a-plano

Open3D `TransformationEstimationPointToPlane`. Normais dos templates estimadas com 30 vizinhos na nuvem alvo completa. Normal de superfície não equivale a plano oclusal; vizinhanças na proximidade entre arcadas e geometria de base podem distorcer normais. Nenhum parâmetro de normal foi ajustado no teste. Candidatos são ranqueados pelo mesmo RMSE simétrico completo da referência.

### (b) Trimmed ICP

Foram comparados descartes de **20% e 30%**. A cada iteração, encontra vizinhos mais próximos source→target dentro de 8 unidades, descarta a fração das correspondências válidas com maior distância, ajusta R/t por Kabsch/SVD com determinante +1 e acumula a transformação. Mínimo seis correspondências. É trim direcional por distância, não identificação de fissura ou anomalia. Candidatos finais são comparados por RMSE simétrico completo; o refinamento ignora os pares removidos, mas o ranking final ainda é sensível às superfícies ausentes.

### (c) Multi-template, 3 ou 5 pares

Templates pareados, superior e inferior do **mesmo paciente-template**, todos exclusivamente do desenvolvimento: **{', '.join(t['id'] for t in templates)}**. Há portanto 3 ou 5 templates por arcada, com relação do par preservada. Escolha farthest-first em seis descritores de extensão das duas arcadas no frame orientado, padronizados somente no desenvolvimento, começando por P016. É diversidade geométrica aproximada, não estratificação clínica/GOSLON.

Cada template é colocado primeiro no referencial comum P016 por uma transformação rígida do par. Não se comparam rotações em referenciais nativos distintos. Cada consulta é refinada contra cada template com os quatro inícios e ponto-a-ponto. Compararam-se:

- **RMSE:** escolhe o template com menor RMSE simétrico;
- **medoid:** mediana rotacional **observada** (medóide) que minimiza a soma das distâncias geodésicas às outras rotações; mantém R/t dessa solução. Não é média de Euler nem mediana componente a componente. Uma maioria de templates enviesados ainda pode gerar uma escolha inconsistente.

### (d) Posterior

Foram comparados os **40% ou 60% posteriores** por projeção no AP estimado, em cada arcada separadamente, tanto no source quanto no alvo. Apenas essa região entra no ICP ponto-a-ponto e no RMSE usado para ranquear candidatos. Assim o critério não reinsere a região anterior excluída. O frame e a translação inicial ainda usam a geometria completa. Recorte assimétrico pode mudar a região selecionada.

**É uma proxy**, removendo a região anterior onde se supõe estar a fissura; não houve segmentação validada da fissura, não se garante que toda fissura esteja fora da máscara, e a inferior não tem a mesma indicação clínica. O nome posterior não certifica uma região anatômica real. Menos região pode aumentar simetrias e perder restrições de orientação.

### Resultado do desenvolvimento e congelamento

Critério fixo: menor média de taxa de falha >5° entre os **17 grupos de conteúdo-paciente** do desenvolvimento, com média dentro dos aliases; desempate pela média das medianas individuais de erro. Os 20 IDs participam, mas cópias não recebem peso extra. Sem seleção por resultados de teste.

| Configuração dev | Falha >5 por conteúdo | Média das medianas | Selecionada |
|---|---:|---:|---|
{devtable}

Configurações levadas ao teste: **{', '.join(selected)}**. Congelamento em **{frozen['utc']}**; `congelamento.json` registra hashes de código, escolhas, divisão e templates antes do teste. `verificar.py` confirma hashes intactos. Resultados não foram usados para alterar algoritmo, templates, máscara, trim, seleção ou limiares.

## Limiares 2°, 3°, 5° e 10°

Taxa de falha é **erro estritamente maior** que o limiar. Tabela com pesos iguais entre conteúdos-paciente e IC95 de bootstrap de grupos; os valores nominais por 20/49 IDs também estão no JSON.

| Conjunto | Método | >2° % [IC95] | >3° % [IC95] | >5° % [IC95] | >10° % [IC95] |
|---|---|---:|---:|---:|---:|
{chr(10).join(rate_rows)}

![CDF teste](resultados/CDF_test.png)

`CDF_test.png` e `CDF_dev.png` mostram a CDF com detalhe 0–15° e domínio 0–180°. Cada paciente-conteúdo tem peso igual. As bandas bootstrap ponto a ponto, 2.000 reamostragens inteiras, estão em `CDF.json`; não são bandas simultâneas. Não houve escolha posterior de um limiar “mais favorável”.

## Porta de qualidade

Não foi recalibrada, aplicada para excluir ensaios ou usada para escolher variante. Registra-se apenas o resultado anterior: **778/980 =79,39% das execuções rejeitadas** na Etapa 3. Todas as execuções desta comparação permanecem na análise.

## Suposições e limites

- Estuda-se consistência com cada baseline, não correção anatômica. Um método pode ser repetível e produzir uma pose inadequada.
- Uma transformação rígida comum preserva a articulação existente; não a valida nem reconstrói uma oclusão ausente.
- Unidades mm, frame vertical/AP/lateral, ruído, recorte, normais, frações de trim/posterior e templates são hipóteses de engenharia.
- Cada variante tem seu próprio baseline; variantes multi-template podem trocar de template entre baseline e ensaio. Isso é parte da instabilidade medida, não foi corrigido usando Q verdadeiro.
- O Q conhecido só participa da avaliação. Não restringe nem escolhe o refinamento.
- O referencial dos componentes é geométrico, não anatômico comprovado; log SO(3) não é decomposição causal de movimentos.
- 20/49 IDs não equivalem a identidades clínicas independentes confirmadas. A análise por 17/47 conteúdos é uma precaução contra pseudorreplicação, não identificação clínica de pacientes.
- O teste já pertence às etapas anteriores, portanto é holdout interno com novas variantes congeladas, não validação externa inédita. Seleção/ajustes só usaram desenvolvimento nesta etapa.
- IC95 são descritivos/exploratórios, pontuais; múltiplas variantes e poucos pacientes limitam inferência. Não se usa n=980 como tamanho amostral independente.
- Não há câmeras de treino preenchidas, classificação GOSLON ou afirmação de alinhamento anatomicamente correto.

## Reprodução e verificações

Implementação: `refinements.py`; entradas/copias em `copias/`, perturbações em `cache/`; `templates/selecao.json` preserva as transformações dos templates. Ambiente local da Etapa 1, sem novas dependências ou chamadas de rede.

```sh
"etapa1/.venv/bin/python" "etapa4/scripts/preparar.py"
"etapa1/.venv/bin/python" "etapa4/scripts/executar.py" dev
"etapa1/.venv/bin/python" "etapa4/scripts/congelar.py"
"etapa1/.venv/bin/python" "etapa4/scripts/executar.py" test --workers 3
"etapa1/.venv/bin/python" "etapa4/scripts/oraculos.py"
"etapa1/.venv/bin/python" "etapa4/scripts/analisar.py"
"etapa1/.venv/bin/python" "etapa4/scripts/verificar.py"
"etapa1/.venv/bin/python" "etapa4/scripts/resumir.py"
```

Não misture checkpoints de configurações diferentes nem recongele após olhar o teste para alegar avaliação intocada. `desenvolvimento/ensaios.json` guarda a grade completa; `teste/ensaios.json` contém apenas as quatro variantes congeladas. Referências Etapa 3 estão em `referencias/`, preservadas.

`verificar.py` confere hashes de 138 cópias/fontes/originais e do congelamento, templates só do desenvolvimento, mesma divisão e Q/u, R em SO(3), Kabsch sintético, reprodução ponto-a-ponto da Etapa 3, norma dos componentes e 292 oráculos. Isso verifica a implementação; não certifica anatomia.
'''
    (OUT/'README.md').write_text(text)
    print('README Etapa 4 gerado.')
if __name__=='__main__':main()
