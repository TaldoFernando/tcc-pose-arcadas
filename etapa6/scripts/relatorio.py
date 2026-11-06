from pathlib import Path
import json,csv
OUT=Path(__file__).resolve().parents[1]
def main():
 perf=json.loads((OUT/'resultados/performance_resumo.json').read_text());sens=list(csv.DictReader((OUT/'resultados/sensibilidade_resumo.csv').open()));indexed={r['parameter']:r for r in sens};demo=json.loads((OUT/'demo_manifest.json').read_text());IDs=', '.join(r['ID'] for r in demo)
 text=f'''# Etapa 6 — renderizador funcional; calibração de treino pendente

**A reprodução das imagens de treino ainda não foi validada.** O renderizador offscreen está implementado e testado. As câmeras originais não foram encontradas, e não existe correspondência confirmada entre os STL disponíveis e o conjunto adicional de imagens de treino. `camera_config.json` mantém todos os parâmetros de treino em **PLACEHOLDER**. Não há métricas reais de validação a reportar: n=0, não erro zero.

## Tabela fornecida em 6 de novembro de 2026

A tabela recebida foi conferida com os arquivos: os 351 registros apontam para pastas locais que contêm as seis vistas. P110, **no namespace da tabela**, foi excluído: suas seis imagens são integralmente pretas, confirmado pixel a pixel. Restam 350 registros e 2.100 vistas de referência utilizáveis para catalogação. Caminhos e dados de origem ficam em `privado/tabela_recebida.txt` e `tabela_imagens_resolvidas.json`.

A tabela contém somente formato `.png`; a coluna Nº do molde usa códigos M001…M351, sem um campo com nome/caminho/hash do STL correspondente. Esses códigos não foram localizados nos caminhos dos STL disponíveis. Portanto a correspondência **tabela→imagens foi resolvida**, mas a correspondência **tabela→STL continua ausente**. IDs Pxxx desta tabela não devem ser unidos automaticamente aos Pxxx atribuídos aos STL na Etapa 5.

`resultados/tabela_recebida_conferencia.csv` explicita ID_tabela, ID_STL ainda vazio e disponibilidade das vistas. `referencias_recebidas_por_ID.csv` registra dimensões e fundo observado por ID da tabela, sem ajustar câmeras. Existem várias resoluções nativas por vista; isso reforça que o Resize(224,224) do código é um passo separado da renderização original. Essas estatísticas descritivas não usam imagens como validação de câmeras nem afirmam pareamento com malhas.

## Fontes locais e bloqueio

A busca cobriu o projeto, os dados extraídos, arquivos e código locais em Desktop, Documents e Downloads. Foram localizados 351 registros completos de seis vistas, todos com tuplas de hashes de arquivos distintas; dez notebooks e dois scripts shell relacionados não contêm parâmetros de câmera. As vistas nesses notebooks são frontal/left/right/up/down/angled. Nove notebooks têm Resize(224,224), documentado em `preprocessamento_operacoes.json`, com fonte e hashes em `fontes_hashes.json`. Isso é pré-processamento da rede, não resolução nativa da câmera; ainda não foi confirmado qual notebook corresponde ao classificador atual. A busca ampliada em 161 arquivos compactados encontrou STL somente no ZIP original já fornecido e nenhum projeto 3D/câmera adicional. Não foram encontrados STL fora do projeto nem vínculos confirmados desses registros com P001–P069. **Códigos numéricos iguais em fontes diferentes não comprovam a mesma pessoa.** Não usamos pareamento por semelhança visual ou pelo número do registro.

O ZIP original contém 42 JPEG (26 hashes de arquivo distintos); há imagens nas pastas associadas a P014, P027, P052 e P055, além de uma imagem sem associação. Essas capturas incluem superfícies coloridas e composições com interface; não há confirmação de que sejam as seis entradas usadas para treinar o classificador. A amostra inspecionada do conjunto adicional mostra material sem textura, com fundo/enquadramento diferentes. STL não contém a textura RGB necessária para recuperar as cores dessas capturas. Não misturamos as duas origens como se fossem o mesmo protocolo.

`resultados/fontes_resumo.json` e `busca_codigo_resumo.json` documentam a busca com identificadores de fonte. Caminhos reais ficam exclusivamente em `privado/`; a correspondência clínica ID→pasta continua em `../etapa5/privado/id_pasta_local.csv`. Arquivos privados não devem ser distribuídos.

Para concluir faltam: STL superior/inferior dos mesmos registros que têm as seis imagens de treino, **ou** uma tabela local comprovando sua correspondência com os IDs existentes; identificação de quais imagens realmente entraram no treino; e, se existir, o gerador original. O formato de entrada está em `manifesto_calibracao_exemplo.json`. São necessários conjuntos de calibração/validação sem conteúdo compartilhado; para a folha pedida, dez IDs de validação completos.

## Situação dos seis pedidos

| Pedido | Situação |
| --- | --- |
| Recuperar parâmetros ou calibrar em pares reais | Busca feita; calibração não executada por falta de pareamento confirmado |
| Mediana/máximo por vista em pacientes externos à calibração | Pendente; `validacao_pendente.csv` contém PLACEHOLDER em todas as métricas |
| Sensibilidade dos parâmetros | Executada somente em câmeras demonstrativas; não estabelece tolerância do treino |
| Offscreen determinístico e tempo | Implementado, executado em dez IDs e verificado por repetição |
| Folha render × treino × diferença para dez pacientes | Folha demonstrativa com células ausentes explicitadas; folha pareada real pendente |
| `camera_config.json` | Salvo com PLACEHOLDER; configuração demonstrativa separada |

## API implementada

`render_views.py` oferece `render_views(mesh, camera_config)` e retorna um dicionário de arrays RGB `uint8`, com chaves exatas Angulada, Direita, Esquerda, Up, Frontal e Inferior. `mesh` é um dicionário `superior`/`inferior` contendo triângulos Nx3x3 ou caminhos STL locais. Uma configuração pode ser um dicionário ou um JSON local. A API retorna vistas por nome; não assumir que a ordem de inserção é a ordem dos tensores do classificador. `ordem_vistas_notebooks.json` registra listas observadas nos códigos relacionados; várias usam frontal/left/right/up/down/angled, e há uma variante com somente quatro vistas. Qual versão é a atual ainda não foi confirmado.

```python
from render_views import render_views

# Falha explicitamente enquanto as câmeras de treino forem PLACEHOLDER.
images = render_views(mesh, "camera_config.json")

# Somente demonstração, sem equivalência de treino:
images_demo = render_views(mesh, "camera_config_experimental.json")
```

A configuração experimental tem `allow_uncalibrated=true` explicitamente. Não usar suas imagens como se reproduzissem o treino. O renderizador não chama normalização, classificador ou rede. Não faz autoenquadramento, rotação, recorte de base nem escala por paciente: o chamador precisa entregar o par no mesmo referencial usado na calibração. Alterar a normalização exige reavaliar as câmeras. Uma única transformação rígida deve ser aplicada às duas arcadas.

O backend é CPU/Numba, z-buffer, projeção ortográfica ou perspectiva, clipping de profundidade, iluminação Lambert controlada, normais suavizadas, material fixo e supersampling determinístico. Não depende de janela, OpenGL, navegador, servidor nem serviço externo. Não reproduz texturas, sombras complexas ou o shader original desconhecido. Luz, material, espaço de cor e tratamento de bases de treino permanecem PLACEHOLDER.

A demonstração usa a transformação multi5_rmse do banco balanceado da Etapa 5, seguida do frame geométrico do P016. Não representa uma escolha validada de protocolo de treino. O enquadramento por vista foi calculado **uma única vez** a partir do template P016, com margem de 15%; não é ajustado para cada paciente. Up mostra superior, Inferior mostra inferior; as outras quatro mostram o par. As convenções direita/esquerda e o ângulo da Angulada são suposições demonstrativas, não recuperadas do treino.

## Demonstração executada e tempo

IDs escolhidos com seed 20261106 entre os 49 IDs disponíveis no resumo da Etapa 5: {IDs}. Foram geradas 60 imagens em `demonstracao/`, usando somente cópias locais de STL.

A 512×512 por vista, supersampling 2× em cada dimensão, material/luz fixos:

- Tempo mediano para seis vistas, malha já preparada: **{perf['six_views_seconds_median']:.3f} s/paciente**.
- Maior tempo: **{perf['six_views_seconds_max']:.3f} s/paciente**.
- Aquecimento medido: {perf['jit_startup_seconds']:.3f} s; o cache Numba já pode estar disponível. Isso não mede uma instalação fria.
- Doze imagens repetidas (seis vistas de dois IDs) idênticas pixel a pixel. Hashes em `determinismo.csv`.

`tempo_por_ID.csv` separa leitura/preparo, renderização das seis vistas e tempo total. Tempos são desta máquina e desta resolução; não são garantia para outro hardware ou resolução de treino, ainda desconhecida.

`resultados/folha_10_IDs_PLACEHOLDER.png` mostra render, treino indisponível e diferença indisponível para dez IDs. **Essa folha não é validação render × treino.** Não fabricamos referências nem diferenças. `contact_sheet.py` está preparado para gerar a folha real, com diferença RGB absoluta amplificada 4× e dez IDs de validação, assim que houver pares confirmados.

## Sensibilidade experimental

`resultados/sensibilidade_experimental.csv` traz perturbações positivas e negativas em todos os componentes de posição, alvo e up, extensão ortográfica, distância, near/far, largura/altura da resolução, canais RGB do fundo e intensidades de luz. Foi usado um ID da demonstração, seis vistas, resolução 256×256, mantendo geometria/material determinísticos.

Posição/alvo: ±0,5 unidade nativa, assumida mm; up: ±0,01 por componente; extensão/distância/near/far: ±1%; resolução: ±1 px; fundo: ±1 RGB; intensidades: ±0,01. Perturbações têm unidades diferentes e não devem ser usadas como uma classificação universal de importância. As comparações de resolução são explicitamente reamostradas de volta à grade de referência apenas neste teste; validação real não faz resize silencioso.

Exemplos do pior efeito entre as seis vistas, nesta demonstração:

| Perturbação | Maior perda de IoU | Maior deslocamento do centroide |
| --- | --- | --- |
| Alvo x ±0,5 | {float(indexed['target_x']['max_one_minus_IoU']):.4f} | {float(indexed['target_x']['max_centroid_px']):.2f} px |
| Extensão ortográfica ±1% | {float(indexed['ortho_height']['max_one_minus_IoU']):.4f} | {float(indexed['ortho_height']['max_centroid_px']):.2f} px |
| Distância ±1%, ortográfica | {float(indexed['camera_distance']['max_one_minus_IoU']):.4f} | {float(indexed['camera_distance']['max_centroid_px']):.2f} px |

Distância ao longo do eixo óptico não é identificável por uma imagem ortográfica; variações dentro do clipping não mudam o enquadramento. Escalar o vetor up também não muda sua direção projetada. A sensibilidade zero desses graus de liberdade é esperada e não recupera seus valores históricos. Não foi testada tolerância de FOV de treino porque nem sua projeção foi confirmada. Gráfico em `sensibilidade_experimental.png`. Os números acima não definem tolerâncias aceitáveis para o classificador.

## Pipeline preparado para calibração real

`calibrate_cameras.py` exige pareamento e origem de treino comprovados no manifesto, calcula hashes dos STL reais para impedir conteúdo compartilhado entre calibração/validação e admite transformações rígidas de entrada previamente fixadas. Não recebe grupo nem GOSLON. Não ajusta pose individual contra a imagem de cada paciente.

Critérios predefinidos em `protocolo_calibracao.json`: comparar ortográfica/perspectiva usando somente calibração; ajustar orientação, roll e deslocamento no plano da imagem, extensão aparente e distância/FOV condicionais na perspectiva; observar resolução nativa e estimar fundo pelos cantos das imagens de calibração. Otimização global seguida de refinamento local, primeiro em grade reduzida e depois na resolução nativa. Não garante ótimo global de um problema não convexo. Distância ortográfica é fixada por convenção geométrica e marcada como gauge não identificável, nunca estimada como parâmetro original de treino.

A função objetivo combina IoU, SSIM, erro de centroide, erro de caixa e escala com pesos declarados no protocolo. Máscaras por diferença de cor em relação ao fundo são heurísticas, não silhuetas anotadas. Textos de interface, sombras, recortes inconsistentes e cores próximas do fundo podem invalidá-las; precisam de inspeção. SSIM inclui material/textura/fundo, portanto não isola erro de câmera. A escala é `100*abs(sqrt(area_bbox_render/area_bbox_treino)-1)`; também há erro relativo máximo entre largura/altura e RMS dos quatro limites da caixa, em pixels.

O pipeline salva configuração e hash antes de abrir imagens de validação. Métricas finais são na resolução nativa: mediana/máximo e também mínimo de IoU/SSIM, pois máximo representa o melhor caso dessas duas métricas. Resolução diferente na validação é incompatibilidade explícita, sem adaptar câmera ao teste. Nenhuma métrica de treino foi calculada nesta entrega.

## Verificação e reprodução

Usar o ambiente local `../etapa1/.venv/bin/python`, com NumPy, Numba, Pillow, SciPy, scikit-image e OpenCV já instalados. Open3D é usado somente no preparo da demonstração para reutilizar o frame da Etapa 5; não é necessário no núcleo do rasterizador.

Na pasta `etapa6/`:

```sh
"../etapa1/.venv/bin/python" "scripts/testar_render.py"
"../etapa1/.venv/bin/python" "scripts/render_demo.py"
"../etapa1/.venv/bin/python" "scripts/sensibilidade.py"
```

Após fornecer um manifesto real com as imagens pareadas e o referencial de entrada fixado:

```sh
"../etapa1/.venv/bin/python" "calibrate_cameras.py" "manifesto_real_local.json" "camera_config_experimental.json" "calibracao_real"
```

O exemplo de manifesto tem lista de registros vazia e falha explicitamente; não é um conjunto fictício de calibração. Material/iluminação originais continuam marcados como desconhecidos mesmo após um ajuste geométrico, até haver fonte para confirmá-los.

`testes_render.json` verifica projeção/escala/deslocamento conhecidos, perspectiva, oclusão por z-buffer, clipping, ausência de mutação e bloqueio de PLACEHOLDER. São testes sintéticos de implementação, não validação em pacientes. `verificacoes.json` registra integridade dos STL, privacidade das saídas e estado pendente da calibração. Não houve envio externo, execução do classificador nem alteração de originais. Os resultados de pose usados na demonstração medem consistência e não certificam correção anatômica.
'''
 (OUT/'README.md').write_text(text);print('README salvo: renderizador funcional, calibração real explicitamente pendente')
if __name__=='__main__':main()
