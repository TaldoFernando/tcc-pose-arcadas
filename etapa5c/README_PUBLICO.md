# Etapa 5C — código público do modelo substituto

Nova divisão do experimento de sensibilidade à pose. Trata-se de um **modelo substituto**, não do Goslon AI. As câmeras do treino original continuam **PLACEHOLDER**; as features locais usam câmeras próprias. Consistência geométrica não demonstra correção anatômica.

Esta pasta pública contém scripts, versões do runtime e o protocolo fixado antes da execução local. Dados, relatórios individuais, lista dos conjuntos por ID, hashes de conteúdos de pacientes, rótulos, imagens, features, pesos e o pacote privado de reprodução não estão publicados. O README clínico local é separado deste documento público.

## Protocolo

- Identidade: usar identificador clínico pseudonimizado validado quando disponível. Na execução documentada não foi encontrado um; o código fornecido implementa o fallback por conteúdo do par. Os IDs de moldes não comprovam identidade de paciente.
- Agrupar aliases por hashes das duas arcadas; excluir todo o conteúdo com divergência em grupo ou GOSLON. Sinalizar proximidade geométrica para revisão manual; essa triagem não valida identidade clínica nem exclui visitas longitudinais da mesma pessoa.
- Bloquear aproximadamente 25% por grupos 1/2/3, seed 20261122, e gravar o hash antes das novas análises de desempenho. Rótulos são lidos antes somente para auditoria de conflitos e estratificação.
- Reservar os cinco conteúdos-template no desenvolvimento, conforme restrição prévia. O sorteio é condicional a essa restrição.
- No desenvolvimento: StratifiedGroupKFold, quatro folds, seeds 20261123–20261127. Aliases e blocos conservadores nunca cruzam conjuntos.
- Treinar a cabeça apenas em pose canônica, com hiperparâmetros fixos, sem selecionar época, variante ou limiar pelo teste.
- Banco global: utilizar a alternativa de sensibilidade excluindo os cinco conteúdos-template da pontuação OOF. O banco não foi reconstruído por fold; a retirada da pontuação não elimina toda a exposição geométrica da validação.
- Calcular tolerância à pose exclusivamente nas predições fora do fold do desenvolvimento. Congelar o modelo final antes da avaliação canônica única do teste.
- Reamostrar pacientes proxy no bootstrap, mantendo juntos os ensaios e as cinco repetições. Esses IC condicionam aos modelos/divisões fixos; não equivalem a retreinar a cadeia em cada reamostragem.
- Desfecho primário: F1 macro canônico do modelo substituto fixo no teste. Demais condições, contrastes e estratos são exploratórios.

O novo teste é bloqueado para esta reanálise interna. Os dados já participaram de análises anteriores; não se trata de um teste externo ou sem exposição histórica. O código não substitui uma confirmação clínica da identidade nem a revisão dos rótulos.

## Entradas locais necessárias

Fornecer apenas localmente e com autorização:

- etapa5/pares_ids.json, etapa5/rotulos_local.csv e cópias das arcadas sob etapa5/copias/.
- Banco geométrico etapa6/stl/modelo_normalizacao.npz.
- Features locais em etapa7b/features/Pxxx.npz e etapa7b/correcoes_v2/features/Pxxx.npz.
- Para a verificação de privacidade, tabela local separada etapa5/privado/id_pasta_local.csv; ela nunca deve ser publicada.

Os scripts de extração e centralização da extensão anterior estão em etapa7b/correcoes_v2/scripts/. A extração exige os ativos e congelamentos locais daquela etapa. Não há download automático de dados ou pesos pela Etapa 5C; um clone público sozinho não executa o experimento completo.

O protocolo está em [plano_previo.json](plano_previo.json). Os nomes de caminhos nesse arquivo são referências a entradas privadas, não dados incluídos no Git. Identificadores fixos dos templates referenciam a implementação; suas geometrias não são distribuídas.

## Execução em cópia limpa

A partir da raiz do projeto, usar um ambiente Python compatível com [requirements.txt](requirements.txt). A lista registra as versões locais; wheels podem variar entre plataformas.

Criar os diretórios de saída, sem copiar resultados de uma execução anterior:

~~~sh
mkdir -p "etapa5c/resultados" "etapa5c/checkpoints" "etapa5c/teste_bloqueado" "etapa5c/qa"
~~~

Com as entradas privadas presentes, executar sequencialmente:

~~~sh
".venv/bin/python" "etapa5c/scripts/preparar.py"
".venv/bin/python" "etapa5c/scripts/congelar_execucao.py"
".venv/bin/python" "etapa5c/scripts/classificador.py" cv
".venv/bin/python" "etapa5c/scripts/avaliar.py"
".venv/bin/python" "etapa5c/scripts/verificar.py"
".venv/bin/python" "etapa5c/scripts/classificador.py" final_fit
".venv/bin/python" "etapa5c/scripts/teste_final.py"
".venv/bin/python" "etapa5c/scripts/relatorio.py"
".venv/bin/python" "etapa5c/scripts/auditar_resultados.py"
".venv/bin/python" "etapa5c/scripts/verificar.py" --final
~~~

O script congelar_execucao.py foi acrescentado após a execução original para automatizar o passo de manifesto que havia sido feito antes do treino. Ele recusa sobrescrever os congelamentos existentes e não altera a cronologia original.

Os scripts recusam sobrescrever a divisão congelada, as predições OOF e o modelo final, ou reabrir o teste. Não apagar esses bloqueios para selecionar resultados melhores. Um hash local assegura integridade, sem constituir pré-registro independente.

## Saídas privadas e interpretação

A execução produz auditoria de conflitos, candidatos geométricos, divisão e folds, tamanhos por conjunto/grupo, predições OOF, sensibilidade sem templates, tolerância à pose, métricas com IC95%, congelamentos, predições finais e matrizes de confusão. Os arquivos individuais contêm somente IDs e permanecem ignorados pelo Git. Avisar quando qualquer classe tiver menos de cinco pacientes proxy no teste.

A taxa de troca compara cada predição com a referência canônica multi5 do próprio modelo e repetição. A centralização ou a troca de referencial também pode mudar a classe em 0°; isso limita a interpretação de um limiar como tolerância puramente angular. O erro ordinal é entre grupos 1/2/3, não entre cinco classes GOSLON.

Os ensaios realistas reutilizados alteram as nuvens do registro por reamostragem, ruído e recorte; a malha renderizada permanece decimada e íntegra. Não interpretar esses ensaios como recorte visual completo da entrada.

Não publicar dados derivados por terem apenas IDs: pseudonimização não equivale a anonimização. O .gitignore permite explicitamente só os arquivos públicos revisados.
