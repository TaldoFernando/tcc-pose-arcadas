"""README com resultados observados e limites explícitos."""
from common import *

def main():
    pairs=load_json('pares.json');selection=load_json('templates/selecao.json');visual=load_json('selecao_visual.json');excluded=load_json('pastas_excluidas.json')
    articulation=list(csv.DictReader((OUT/'articulacao.csv').open()));robust=load_json('resultados/robustez_resumo.json');disp=load_json('resultados/dispersao_resumo.json');worse=list(csv.DictReader((OUT/'resultados/casos_piora.csv').open()));comparison=list(csv.DictReader((OUT/'resultados/comparacao_metodos.csv').open()))
    plausible=sum(p['parece_articulado'] for p in pairs);unique=len({(p['superior']['sha256'],p['inferior']['sha256']) for p in pairs});n=len(pairs)
    robusttable='\n'.join(f"| {m} | {v['todos_pares']['n']} | {v['todos_pares']['media']:.3f} | {v['todos_pares']['desvio_populacional']:.3f} | {v['todos_pares']['max']:.3f} | {v['todos_pares']['falhas_maior5']} | {100*v['todos_pares']['taxa_falha_maior5']:.2f}% |" for m,v in robust.items())
    disptable='\n'.join(f"| {m} | {v['pacientes_pastas_unicos']} | {v['pares']} | {v['min']:.3f} | {v['mediana']:.3f} | {v['max']:.3f} |" for m,v in disp.items())
    worsetext=[]
    for method in ['superior','combinada']:
        wt=[r for r in worse if r['metodo']==method and r['piorou_template_mais_0_1grau']=='True'];wp=[r for r in worse if r['metodo']==method and r['piorou_peer_mais_0_1grau']=='True']
        worsetext.append(f"- **{method}**: {len(wt)} pioraram em distância ao template ({', '.join(r['id'] for r in wt) or 'nenhum'}); {len(wp)} pioraram na mediana das distâncias aos outros pacientes ({', '.join(r['id'] for r in wp) or 'nenhum'}).")
    large_rotations=[(r['id'],m,float(r['rotacao_aplicada_'+m+'_graus'])) for r in comparison for m in ['superior','combinada'] if float(r['rotacao_aplicada_'+m+'_graus'])>90]
    rotation_alerts='; '.join(f'{identifier} ({m}: {angle:.2f}°)' for identifier,m,angle in large_rotations) or 'nenhum'
    per_table=[]
    for identifier in sorted(set(r['id'] for r in worse if r['piorou_template_mais_0_1grau']=='True' or r['piorou_peer_mais_0_1grau']=='True')):
        for r in worse:
            if r['id']==identifier:per_table.append(f"| {identifier} | {r['metodo']} | {float(r['delta_template_graus']):+.2f}° | {float(r['delta_peer_graus']):+.2f}° |")
    pairlist='\n'.join(f"| {p['id']} | {p['paciente']} | {p['status_articulacao']} |" for p in pairs)
    errors=[float(r['angulo_entre_solucoes_graus']) for r in comparison]
    text=f'''# Etapa 2 — articulação e consistência da normalização do par

Processamento local, somente em cópias. Não houve envio a serviços externos. As seis câmeras de treino permanecem **PLACEHOLDER** e as seis vistas não foram renderizadas. Os PNG desta etapa são apenas vistas geométricas para revisão.

**Resultado principal:** a referência combinada teve menos falhas sob perturbações, mas a taxa de erro >5° permaneceu em {100*robust["combinada"]["todos_pares"]["taxa_falha_maior5"]:.2f}% (superior: {100*robust["superior"]["todos_pares"]["taxa_falha_maior5"]:.2f}%). Portanto, o protocolo atual evidencia **consistência limitada**, não robustez suficiente garantida. As medianas de dispersão diminuíram, mas os máximos aumentaram nas duas referências.

## Escopo e integridade

Foram incluídas **{n} pastas com um conteúdo superior e um inferior identificados**, correspondentes a **{unique} pares únicos por SHA-256 das duas arcadas**. Há {len(excluded)} pastas excluídas por ausência de identificação inequívoca das arcadas (`pastas_excluidas.json`); os indeterminados sem decisão humana não foram reclassificados. Pastas com conteúdo repetido não são pacientes distintos confirmados. Os hashes não confirmam identidade/sessão.

`pares.json` liga IDs, nomes, fontes da etapa 1, hashes e cópias em `copias/Pxxx/`. `manifesto_copias.json` registra também os caminhos originais. `validacao_integridade.json` verifica por SHA-256 que cópias, fontes da etapa 1 e STL originais continuam idênticos depois do processamento. Não houve correção, corte ou reescala dos originais. A decimação está apenas no cache de experimentos/prévias.

## 1. Articulação nas coordenadas originais

**{plausible}/{n} pares parecem articulados pela triagem geométrica**; {n-plausible} exigiram registro manual. O maior mínimo aproximado observado foi **{max(float(r['distancia_min_aproximada']) for r in articulation):.4f} unidade**, supondo mm.

`articulacao.csv` contém distância mínima aproximada, percentil 1 das distâncias, fração da superfície amostrada a <=1 unidade da arcada oposta, interseção e razão de sobreposição das bounding boxes em XYZ, volume de interseção e deslocamentos dos centroides, inclusive AP em Y nativo.

A distância usa todos os vértices únicos e 20.000 pontos uniformes por área de cada arcada contra a superfície triangular da outra (Open3D RaycastingScene, bidirecional). **É uma aproximação e um limite superior da distância mínima exata entre triângulos**, não uma solução exata aresta–aresta. Não é distância apenas entre duas nuvens. A resolução interna de consultas é float32. Valor perto de zero pode significar contato ou interpenetração; não foi certificado volume de colisão em malhas abertas. Bounding boxes também não medem colisão real.

Critérios operacionais, não validados clinicamente: mínimo aproximado <=1,5; interseção X e Y >=65% da menor extensão correspondente; deslocamento AP de centroides <=25% da profundidade média; deslocamento lateral <=15% da largura média; centroide superior acima do inferior em Z nativo. Os eixos nativos X/Y/Z são assumidos aproximadamente lateral/AP/vertical, observação compatível com o conjunto, não referencial anatômico comprovado. A relação AP não é medida de overjet.

Há registros de mordida associados a três pares completos. Como todos passaram na triagem, nenhum precisou deles para resgate. O código consulta o registro nas coordenadas nativas, quando um par falha, e verifica suporte de superfície nas duas arcadas; se não sustenta a articulação, mantém **requer registro manual**. Não se estima automaticamente oclusão a partir de um registro deslocado ou não registrado. Esse ramo não foi exercitado pelo conjunto atual e não é um mecanismo validado de reconstrução da mordida.

### Previews dos 15 sorteados

Seed fixa **20261105**, sem reposição entre os 69 IDs físicos. IDs: {', '.join(visual['originais_15'])}. Cada PNG em `previews_originais/` mostra as duas arcadas juntas, sem qualquer transformação de pose: superior azul, inferior laranja. `previews_originais/contato_15.png` reúne os 15. Não houve recenter/reescala independentes das arcadas para desenhá-las. A redução quadric da malha é só visual; as medidas usam as cópias integrais.

## 2. Uma transformação para o par; comparação das referências

`pose_normalize_pair.py` compara:

1. **superior**: calcula a pose usando só a superior e o template superior;
2. **combinada**: calcula a pose a partir das duas nuvens, com contribuição igual das arcadas no baseline (1.024 pontos de cada). Após recortes independentes, as contagens podem diferir.

Em ambos os casos, **o mesmo R e o mesmo t são aplicados às duas arcadas**: `x_saida = R @ x_entrada + t`. Não há ajuste independente da inferior, reflexão nem escala. Isso preserva a articulação original, mas também preservaria um desencaixe original; uma transformação rígida comum não pode articular arcadas que estavam soltas.

Template **{selection['id']} — {selection['paciente']}**, com as duas arcadas do mesmo paciente/pasta e mesma relação nativa. Escolha: medoide angular dos eixos PCA superiores entre os {selection['pares_unicos_elegiveis']} pares únicos que passaram na triagem, distância média {selection['distancia_media_graus']:.3f}°. A escolha por orientação é provisória, não seleciona “melhor anatomia” nem classe clínica.

O centro de saída é a média dos centroides das duas amostras do template; os dois métodos compartilham exatamente essa origem. Os eixos finais mantêm a orientação geométrica nativa do template. Não há afirmação de plano oclusal ou eixos anatômicos corretos.

PCA é recalculada, quatro sinais próprios são testados, cada candidato passa por ICP point-to-point Open3D (sem escala, 60 iterações máximas, distância máxima 8 unidades). Escolha pelo RMSE simétrico completo de vizinhos mais próximos, sem corte; RMSE de inliers e fitness são preservados. `resultados/normalizacoes.json` contém R/t e todos os candidatos por par/método. `resultados/invariancia_articulacao.csv` verifica preservação numérica de distâncias cruzadas entre pontos das arcadas.

`resultados/comparacao_metodos.csv` compara as duas soluções: diferença angular mediana **{np.median(errors):.3f}°**, máxima **{max(errors):.3f}°**. RMSE superior e RMSE combinado medem conjuntos diferentes e não devem, isoladamente, determinar o método vencedor.

## 3. Robustez com variações independentes

**20 ensaios por par e por método: 2.760 normalizações perturbadas**. Cada par usa rotações Haar uniformes em SO(3) e translações uniformes em [−100,100] por eixo. Cada ensaio introduz simultaneamente:

- nova amostragem uniforme da superfície decimada, 2.048 pontos por arcada, semente independente da amostra baseline e independente por arcada/ensaio;
- ruído gaussiano isotrópico independente, sigma **0,15 unidade**;
- remoção de **10–30% dos pontos de cada arcada**, independentemente, escolhendo uma âncora aleatória e removendo a vizinhança espacial mais próxima; é uma região euclidiana, não uma região geodésica certificada;
- decimação quadric real das malhas, dois níveis em cache com meta `min(30000, max(4000, n_faces * 0.5 ou 0.2))`, nível sorteado por arcada/ensaio. Em malhas grandes, os dois níveis podem atingir o mesmo teto; o número real de faces está em cada ensaio.

A decimação é pré-calculada nas cópias nativas e a geometria resultante recebe a rotação/translação conhecida. Isso evita redecimar milhares de malhas; não testa efeitos numéricos do algoritmo de decimação sob orientação diferente. Não é apenas rotação da mesma nuvem: os pontos, a superfície aproximada, o ruído e os recortes diferem do baseline. Os dois métodos recebem os mesmos dados perturbados em cada ensaio, tornando a comparação pareada. O template fica fixo.

Erro angular geodésico: `acos(clip((trace((R1 @ Q) @ R0.T) - 1) / 2, -1, 1))`, comparando com a normalização do par original. Erro de translação: `norm(R1 @ u + t1 - t0)`. Falha: erro estritamente >5°. Desvio padrão populacional. Todos os parâmetros, seeds e Q/u/R/t estão em `resultados/robustez_ensaios.csv` e `parametros.json`.

| Referência | Ensaios | Média (°) | Desvio (°) | Máximo (°) | Falhas >5° | Taxa |
|---|---:|---:|---:|---:|---:|---:|
{robusttable}

`resultados/robustez_por_par.csv` mostra as métricas por paciente/pasta; `robustez_resumo.json` também traz resumos sem duplicatas e sem o próprio paciente-template. O resumo principal mantém o peso dos 69 pares físicos. Não há separação causal dos efeitos: ruído, recorte, reamostragem e decimação foram aplicados juntos. Os 20 ensaios de um paciente não são 20 pacientes independentes.

![Robustez por superior](resultados/histograma_robustez_superior.png)
![Robustez combinada](resultados/histograma_robustez_combinada.png)

## 4. Dispersão entre pacientes, antes e depois

Usam-se exatamente os mesmos **{disp['antes']['pacientes_pastas_unicos']} pares únicos elegíveis** nas três condições. Eixos PCA **exatos da superfície da superior**, obtidos no inventário inicial, são transformados por R; translação não altera eixos. Distância angular é minimizada entre os quatro sinais próprios, como no Passo 0. Isso mede eixos geométricos e pode esconder ambiguidades de 180°; os erros geodésicos dos ensaios não removem essas ambiguidades.

A referência anterior (mediana 9,61°, máximo 35,55°) incluía todas as superiores únicas, inclusive fora do subconjunto de pares completos. A comparação principal abaixo recalcula o “antes” no mesmo subconjunto, para evitar diferença de composição. Mantêm-se variação de forma, bases e sensibilidade de PCA a autovalores próximos.

| Condição | Pares únicos de pacientes | Comparações | Mínimo (°) | Mediana (°) | Máximo (°) |
|---|---:|---:|---:|---:|---:|
{disptable}

![Comparação de dispersão](resultados/dispersao_comparacao.png)

### Casos em que piorou

“Piorou” significa aumento >0,1° (tolerância numérica/operacional explicitada), medido separadamente como distância dos eixos ao template e mediana das distâncias aos outros pacientes. Não significa piora clínica. `resultados/casos_piora.csv` lista todos os IDs, nomes e deltas, inclusive os que melhoraram; `resultados/dispersao_pares.csv` permite auditar cada comparação.

{chr(10).join(worsetext)}

| ID | Referência | Δ distância ao template | Δ mediana aos outros |
|---|---|---:|---:|
{chr(10).join(per_table) if per_table else '| — | — | Nenhum caso >0,1° | — |'}

**Alerta complementar sem remover a ambiguidade de sinal:** rotações aplicadas >90° no baseline: {rotation_alerts}. O conjunto nativo tem poses semelhantes; esses casos devem ser revisados, sem presumir correção anatômica. A métrica PCA com quatro sinais pode ocultar trocas de direção de 180°. A rotação completa consta em `comparacao_metodos.csv` e há PNG suplementar `revisao_normalizados/ALERTA_ID_metodo.png`, fora do sorteio de 20 pacientes.

## 5. Folha de contato para orientadora

Sorteio sem reposição com seed fixa 20261105, no mesmo gerador após o sorteio dos 15 originais. IDs: {', '.join(visual['normalizados_20'])}. A seleção não usa resultado de robustez nem remove casos difíceis.

`revisao_normalizados/contato_20.png` reúne todos os 20. Para impressão/zoom, `folha_01.png` a `folha_04.png` têm cinco pacientes cada; há PNG individual por ID. Cada linha traz frontal, lateral e oclusal **geométricas**, superior azul/inferior laranja. O método **combinada** foi pré-escolhido para esta revisão, antes dos resultados, por usar as duas arcadas. A comparação quantitativa com a referência superior permanece nos CSV; a folha não declara um vencedor anatômico.

Esses nomes de vista assumem os eixos geométricos do template. **Não são as seis vistas de treino** e não estabelecem enquadramento, escala ou referencial anatômico de treinamento. Nenhuma câmera em `config.json` foi preenchida.

## Suposições e alcance

- Unidade mm, correspondência X/Y/Z a lateral/AP/vertical, limiares de articulação, sigma do ruído e cortes são suposições de engenharia.
- Pareamento por pasta e arquivos nomeados não confirma paciente/sessão. Não foram inferidos pareamentos clínicos dos indeterminados.
- Contato, bounding box e AP por centroides não certificam oclusão. Interpenetrações locais não foram quantificadas como colisão volumétrica.
- Uma transformação comum preserva a relação existente; não corrige uma relação incorreta. O ramo de registro de mordida não foi necessário nem validado neste conjunto.
- Template é provisório e sua inclusão facilita seu próprio alinhamento; por isso há resumo adicional sem template.
- Menor dispersão PCA pode resultar do próprio método de alinhamento. Consistência de pose e estabilidade sob perturbações não demonstram exatidão anatômica, validade clínica ou reprodução do treino.
- RMSE não é erro de landmarks. Não houve anotação clínica de referência, avaliação de GOSLON nem escolha de câmeras.

## Reprodução local

Reutiliza o ambiente isolado da etapa 1: Open3D 0.18.0, NumPy 1.26.4, SciPy 1.13.1, Matplotlib 3.9.4, Pillow 11.3.0. Nenhuma instalação ou chamada de rede é necessária neste ambiente.

```sh
"etapa1/.venv/bin/python" "etapa2/scripts/preparar.py" > "etapa2/preparacao.log" 2>&1
"etapa1/.venv/bin/python" "etapa2/scripts/robustez.py" > "etapa2/robustez.log" 2>&1
"etapa1/.venv/bin/python" "etapa2/scripts/analisar.py" > "etapa2/analise.log" 2>&1
"etapa1/.venv/bin/python" "etapa2/scripts/figuras.py" > "etapa2/figuras.log" 2>&1
"etapa1/.venv/bin/python" "etapa2/scripts/verificar.py" > "etapa2/validacao.log" 2>&1
"etapa1/.venv/bin/python" "etapa2/scripts/resumir.py"
```

O processamento de robustez retoma por pares completos. Para alterar parâmetros, use uma nova pasta de resultados/execução; não misture checkpoints de configurações diferentes. O cache de geometria não transforma nem sobrescreve STL. A função pública `normalize_pair()` e a CLI em `pose_normalize_pair.py` retornam uma transformação comum e o RMSE, sem upload nem gravação das malhas originais.

`verificar.py` verifica R/Q em SO(3), composição de transformação conhecida em par sintético, contagens de ensaios, recortes efetivos, invariância de distâncias entre arcadas após os R/t reais, integridade completa por SHA-256 e existência dos PNG/folhas.

## Identificação dos pares

| ID | Paciente/pasta | Triagem |
|---|---|---|
{pairlist}
'''
    (OUT/'README.md').write_text(text)
    print('README Etapa 2 gerado.')
if __name__=='__main__':main()
