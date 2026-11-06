# Consistência de pose de pares de arcadas STL

Código de pesquisa para inspeção de malhas, registro rígido de pares de arcadas, ensaios de consistência de pose, renderização de seis vistas e um protótipo Flask para revisão local. Este repositório público contém **código e configurações selecionadas**. Não contém STL, nuvens de pontos, templates geométricos de pacientes, imagens individuais, rótulos por paciente ou tabelas de identificação.

**Consistência geométrica não significa correção anatômica.** A ferramenta é de apoio à pesquisa e não substitui julgamento clínico. As câmeras do treino original permanecem PLACEHOLDER. O experimento de classificação implementado é um **modelo substituto**, não o Goslon AI; a aplicação Flask usa um stub sem classe estimada.

## Organização

| Pasta | Finalidade |
|---|---|
| `scripts/`, `etapa1/` | Inventário de STL, pareamento e ensaios iniciais |
| `etapa2/`, `etapa3/` | Registro do par, regras de orientação e diagnóstico |
| `etapa4/`, `etapa5/` | Variantes de refinamento, medidas repetidas e estratificação |
| `etapa6/` | Renderização offscreen e câmeras próprias |
| `etapa7/`, `etapa7b/` | Contratos de avaliação e experimento com modelo substituto |
| `etapa8/` | Ferramentas para marcação humana no 3D Slicer |
| `etapa9/` | API Flask, interface Three.js e normalização integrada |
| `etapa10/` | Código para consolidação, figuras e rastreabilidade para o TCC |

Os relatórios locais históricos, congelamentos que relacionam indivíduos e fontes tabulares clínicas não são publicados. Os scripts de análise precisam dessas entradas privadas para reproduzir o estudo. Identificadores de templates presentes em configurações são referências de implementação; suas geometrias não estão neste repositório.

## Ambiente e execução local

Python e as dependências do protótipo estão registrados em `etapa9/requirements.txt`. Para um ambiente compatível:

```sh
python3 -m venv ".venv"
".venv/bin/python" -m pip install -r "etapa9/requirements.txt"
```

Open3D e demais bibliotecas precisam ter suporte para a versão de Python e a plataforma utilizadas. As versões registradas correspondem ao ambiente local do estudo, não a todas as plataformas possíveis. Outros scripts de classificação/documentos têm dependências adicionais.

Para disponibilizar a aplicação após fornecer **localmente e com autorização** os ativos privados esperados:

```sh
".venv/bin/python" "etapa9/app.py"
```

A interface usa `http://127.0.0.1:8765`. **Um clone público sozinho não contém o banco congelado `etapa6/stl/modelo_normalizacao.npz` nem as referências de imagem**; portanto não executa a normalização completa sem esses ativos. O código não baixa dados clínicos, não substitui os templates ausentes por exemplos de pacientes e não fornece pesos de um classificador GOSLON. As verificações de integridade dos ativos devem ser preservadas.

Os uploads são tratados em memória pelo Flask local, inclusive os maiores que o limiar padrão de spool do Werkzeug. Não há gravação de STL pelo endpoint. Isso não constitui auditoria LGPD ou garantia de apagamento forense de memória/swap. Não exponha este servidor de desenvolvimento como serviço clínico público.

## Métodos e limites

Uma transformação rígida comum é aplicada às duas arcadas, sem escala ou espelhamento. A variante multi5_rmse seleciona entre templates de desenvolvimento pelo menor RMSE simétrico. Os indicadores de qualidade são consultivos e não usam a porta histórica como filtro único.

Os ensaios geométricos são relativos à normalização não perturbada do próprio método. Repetições do mesmo conteúdo não são pacientes independentes; os scripts tratam aliases e bootstrap por conteúdo-paciente. Rótulos extraídos da organização local exigem revisão clínica. No modelo substituto, o banco geométrico global limita a independência da cadeia completa em validação cruzada. Não há validação externa ou anatômica concluída.

Landmarks exibidos no protótipo são mock, não marcações clínicas. As ferramentas da Etapa 8 destinam-se à correção e validação por pessoas; não usar landmarks de teste para reajustar normalizadores.

## Testes

Os testes de integração históricos requerem dados privados locais; não estão acompanhados de STL no repositório público. A inspeção sintática pode ser executada sem abrir dados:

```sh
python3 -m compileall -q "scripts" "etapa1" "etapa2" "etapa3" "etapa4" "etapa5" "etapa6" "etapa7" "etapa7b" "etapa8" "etapa9" "etapa10"
```

O código de consolidação da Etapa 10 também depende das fontes sanitizadas do pacote local, que não foram transferidas automaticamente para este repositório. A publicação do código não equivale à disponibilização pública dos dados do estudo.

## Política de publicação

O `.gitignore` usa uma lista explícita de arquivos permitidos. Novos arquivos ficam ignorados por padrão e precisam de revisão antes de serem adicionados. Não usar `git add -f` para contornar essa proteção com dados clínicos. Não publicar diretórios de dados, cópias de malha, caches, features, pesos derivados, previews, rótulos individuais, tabelas privadas, relatórios de QA com dados de paciente ou o pacote local de reprodução.

Three.js, STLLoader e OrbitControls são distribuídos localmente em `etapa9/static/vendor/`, com licença e manifesto preservados. O funcionamento da interface não depende de CDN.
