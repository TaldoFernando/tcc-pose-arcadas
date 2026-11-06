from pathlib import Path
import json,csv
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'etapa6';OUT=BASE/'stl'
def main():
 s=json.loads((OUT/'resumo.json').read_text());cfg=json.loads((BASE/'camera_config.json').read_text());sens=json.loads((OUT/'sensibilidade_status.json').read_text());rows='\n'.join(f"| {g} | {r['n_IDs']} | {r['n_images']} | {r['median_render_seconds']:.3f} |" for g,r in s['groups'].items())
 text=f'''# Etapa 6 — protocolo padronizado somente com STL

**Escopo atualizado pelo usuário:** ignorar as imagens anteriores e gerar seis vistas a partir dos moldes STL, organizadas nos grupos 1, 2 e 3 fornecidos. Os grupos são rótulos da organização recebida; o código não diagnostica nível de fissura e não converte grupo em GOSLON. Não se depende mais do pareamento com imagens antigas.

Foram processados **69 pares superior/inferior**, com 64 conteúdos únicos por hash, e geradas **414 imagens RGB**. Tudo foi executado localmente, em cópias, sem envio externo e sem modificar originais. Saídas usam somente IDs; a tabela ID→pasta permanece em `../etapa5/privado/id_pasta_local.csv`.

| Grupo fornecido | IDs/pares | Imagens | Mediana das seis vistas (s) |
| --- | --- | --- | --- |
{rows}

A separação por grupo serve para pastas, rótulos e revisão visual. **Normalização, câmeras, luz, material e resolução são os mesmos para os três grupos.** O teste de trocar o valor de grupo confirmou que os pixels permanecem idênticos.

## API funcional

`stl_views.py` é a API completa: recebe os STL, aplica uma transformação rígida única às duas arcadas e retorna seis arrays RGB uint8, nomeados Angulada, Direita, Esquerda, Up, Frontal e Inferior. O grupo não é argumento geométrico.

```python
from stl_views import render_views

# Usar cópias locais. O par deve preservar sua relação original de coordenadas.
mesh = {{"superior": "/caminho/local/P001/superior.stl",
        "inferior": "/caminho/local/P001/inferior.stl"}}
images = render_views(mesh, "/caminho/do/projeto/etapa6/camera_config.json")
```

`normalize_pair(mesh, camera_config)` expõe separadamente o par transformado e R, t, RMSE e template escolhido. `render_views.py` continua sendo o rasterizador de baixo nível para uma malha **já normalizada**; não aplicar a API completa novamente em um par já transformado.

## Protocolo definido pelos STL

`camera_config.json` tem status **STANDARDIZED_STL**: seus parâmetros agora são escolhas explícitas de um novo protocolo, não placeholders de execução. Não foram calibrados para reproduzir imagens antigas, desconsideradas por orientação do usuário. A equivalência com o classificador/treino anterior não foi avaliada; seus parâmetros históricos continuam desconhecidos, sem bloquear este protocolo novo.

Normalização: multi5_rmse com o banco geométrico original da Etapa 4 (P016, P004, P045, P029, P002), escolhido só no desenvolvimento. Cada candidato usa os mesmos inícios geométricos e ICP ponto-a-ponto; escolhe-se o menor RMSE simétrico. R/t são convertidos para o frame comum de P016 e então para os eixos canônicos. Não há espelhamento, escala nem ajustes por grupo. Não se refizeram trim_20, posterior_60 ou porta de qualidade. A relação original entre as duas arcadas é preservada; não foi criada uma nova articulação de mordida.

As câmeras foram definidas pelos limites das malhas normalizadas dos **20 IDs originais de desenvolvimento**, com margem fixa de 20%. Foram congeladas antes de avaliar enquadramento/renderização dos 49 IDs de teste. Nenhum conteúdo idêntico atravessa essa divisão. Não há autozoom, recorte ou centralização individual após a normalização. Tamanho e diferenças geométricas entre modelos são preservados.

- Projeção ortográfica, resolução 512×512 por vista, supersampling 2× por dimensão.
- Frontal: câmera no lado anterior do frame geométrico; Direita/Esquerda: +X/−X canônico.
- Angulada: azimute 35° e elevação 20°, escolhas explícitas do protocolo.
- Up mostra apenas a superior; Inferior, apenas a inferior; as outras quatro mostram o par.
- Fundo RGB [32,32,32], material [220,220,220], ambiente 0,35 e difusa 0,65, luz relativa à câmera fixa.
- Distância 200 unidades, clipping 0,1–1000, sem cortar bases ou triângulos dos STL. Em ortográfica a distância é uma convenção, não controla a escala aparente.

A lateralidade clínica não foi certificada: os nomes Direita/Esquerda representam os lados do frame geométrico definido. A hipótese de mm continua baseada na escala dos STL; o formato não declara unidade. Os resultados medem **consistência**, não correção anatômica.

## Resultados e revisão

Imagens: `stl/imagens/grupo_1/P001/...`, com a mesma estrutura para os outros grupos e IDs. Cada par tem seis PNG sem texto ou cor de grupo embutidos. O manifesto contém caminhos relativos, hashes e a divisão desenvolvimento/teste.

- `stl/folha_10_IDs.png`: dez IDs escolhidos com seed fixa, quatro do grupo 1, três do 2 e três do 3.
- `stl/contato_grupo_1.png`, `contato_grupo_2.png`, `contato_grupo_3.png`: revisão de todos os IDs por grupo.
- `stl/rotulos.csv`: ID e grupo conforme a organização fornecida, sem nomes originais.
- `stl/transformacoes.json`: R, t, RMSE, template e tempo de normalização por ID.
- `stl/manifesto_imagens.csv`: 414 imagens com hashes de arquivo/pixels.
- `stl/enquadramento.csv`: fração dos vértices fora do campo por vista. **Nenhum dos 69 pares apresentou vértices fora do enquadramento**, inclusive nos 49 IDs de teste. Isso verifica limites geométricos, não anatomia/oclusão.

Mediana da normalização: **{s['median_normalization_seconds']:.3f} s/par**. Mediana das seis vistas, com malha preparada: **{s['median_six_views_seconds']:.3f} s/par** nesta máquina. `stl/tempo_por_ID.csv` separa normalização, preparo e render. Tempos incluem disputa de CPU entre oito processos; não são promessa de desempenho em outro ambiente. Dezoito imagens, seis vistas de três IDs, foram novamente geradas pela API e deram pixels idênticos aos PNG salvos.

## Sensibilidade sem imagens antigas

`stl/sensibilidade_por_ID.csv` e `sensibilidade_resumo.csv` medem mudanças da imagem renderizada contra sua própria imagem de base, com três IDs (um de cada grupo), seis vistas, resolução 256×256 e {sens['n_perturbations']} perturbações. Isso mede sensibilidade do protocolo, não similaridade ao treino antigo ou acurácia do classificador. `stl/sensibilidade.png` resume a perda de IoU/SSIM; `stl/sensibilidade_exemplos.png` mostra base, imagem perturbada e diferença amplificada.

Foram perturbados componentes de posição/alvo (±0,5 unidade), up (±0,01), extensão ortográfica/distância/near/far (±1%), resolução (±1 px), fundo (±1 por canal RGB) e intensidade ambiente/difusa (±0,01). Todas as condições compartilham a mesma malha e material. Mudanças de resolução são explicitamente reamostradas à grade original apenas para essa comparação. FOV não se aplica à projeção ortográfica. A distância ao longo do eixo óptico e a magnitude de up têm graus de liberdade que podem deixar os pixels invariantes; isso não é erro de cálculo.

IoU/SSIM aqui comparam duas renderizações do mesmo STL. Não há IoU/SSIM contra imagens reais de treino nem folha render×treino×diferença, pois essas referências foram retiradas do escopo.

## Duplicatas e arquivos fora dos pares

P021 e P039 contêm os mesmos STL, mas estão rotulados nos grupos 1 e 2. Preservamos a classificação fornecida e registramos o conflito em `stl/duplicatas_conteudo.csv`; nenhuma categoria foi corrigida automaticamente. Os 69 IDs incluem cinco conteúdos repetidos e não devem ser tratados como 69 moldes independentes em uma avaliação estatística. A divisão herdada mantém duplicatas juntas.

Dos 158 STL físicos originais, 138 entram nos 69 pares inequívocos. Os outros 20 — 12 indeterminados, quatro registros de mordida, três superiores e um inferior adicionais — estão listados somente por ID de arquivo em `stl/arquivos_fora_dos_pares.csv`. Não inventamos pareamentos para eles nem os tratamos como pares completos de seis vistas.

## Reprodução e auditoria

Ambiente local já instalado: `../etapa1/.venv/bin/python`; NumPy, SciPy, Open3D, Numba, Pillow, scikit-image e OpenCV. Backend CPU offscreen, sem janela, navegador ou serviço remoto.

Na pasta do projeto:

```sh
"etapa1/.venv/bin/python" "etapa6/stl/scripts/gerar.py"
"etapa1/.venv/bin/python" "etapa6/stl/scripts/sensibilidade.py"
"etapa1/.venv/bin/python" "etapa6/stl/scripts/verificar.py"
```

`stl/congelamento.json` registra hashes das câmeras, do banco de normalização e do código antes da renderização de avaliação. `stl/verificacoes.json` confirma hashes congelados, rotações próprias, divisão por conteúdo, 414 PNG, repetição determinística, independência em relação ao grupo, integridade dos 158 originais e das 138 cópias, e ausência de nomes de pacientes nas saídas públicas. Nenhum classificador foi treinado ou executado.

A busca anterior de imagens e sua calibração pendente foram substituídas como objetivo atual. Seus arquivos permanecem como histórico; `historico/README_busca_imagens.md` e `camera_config_sem_pareamento.json` guardam o estado anterior. Não executar o antigo `scripts/preparar_demo.py` para reproduzir este protocolo: ele pertence ao experimento histórico. O arquivo ativo é `camera_config.json` e o fluxo ativo está em `stl/scripts/`.
'''
 (BASE/'README.md').write_text(text);(OUT/'README.md').write_text('# Resultados do protocolo STL\n\nConsulte o README ativo em `../README.md`.\n');(BASE/'estado_atual.json').write_text(json.dumps({'scope':'STL_ONLY_STANDARDIZED','user_request':'ignore old reference images; use STL groups 1/2/3','camera_config':'camera_config.json','API':'stl_views.py:render_views','results':'stl/','n_pairs':69,'n_images':414,'legacy_image_calibration_blocker_removed':True},indent=2));print('README ATIVO ATUALIZADO: protocolo STL, grupos informados e imagens geradas')
if __name__=='__main__':main()
