# Etapa 8 — marcação humana e avaliação geométrica A1/T1

A execução atual usa um avaliador e uma sessão, **A1/T1**, com
`confiabilidade=nao_avaliada`. A2, T2, intervalo de 14 dias e ICC não são
requisitos para avançar. Uma função adicional de revisão independente de A2
precisaria ser definida separadamente; não se infere concordância a partir de
aprovação coletiva.

## Código e contratos

- `a1t1_v4/executar.py`: auditoria, congelamento e avaliação geométrica de A1/T1.
- `a1t1_v4/plano_execucao.json`: regras da execução, métricas e bootstrap.
- `slicer_markups.py` e `etapa8_painel_visual.py`: posicionamento manual e
  confirmação individual; separação visual das arcadas sem alterar coordenadas
  analíticas. O painel requer o 3D Slicer.
- `apoio_edicao.py`: ocultação de propostas não selecionadas e histórico de
  movimentos iniciado ao ativar a ajuda; não recupera movimentos anteriores.
- `e8_common.py`, `coleta.py`, `congelar_definicoes.py`: validação de referências,
  datas, fases, protocolo versionado, hashes, template e transformações rígidas.
- `analisar.py` e `coleta24_v3/gerenciar.py`: contratos históricos preservados;
  **não são a porta de avanço da execução A1/T1**.

O plano clínico e os arquivos protegidos pelo congelamento não são reescritos
para eliminar pendências. A execução A1/T1 os consulta para validar as entradas
e registra seus próprios requisitos. Pilotos e template ficam fora da análise
principal. Se houver menos exportações válidas que os IDs previstos no plano
original, os resultados são identificados como parciais e os IDs faltantes
ficam listados somente no relatório local. Uma entrada inválida ou duplicada
continua bloqueando a análise; a ausência de A2/T2 não bloqueia.

## Entradas locais e execução

O clone público não contém STL, coordenadas humanas, template geométrico,
rótulos, partições individuais, perfis clínicos aprovados, congelamentos com
proveniência individual ou resultados por molde. O estudo só pode ser
reproduzido com as entradas locais autorizadas e seus hashes originais:

- plano e amostra de coordenação, transformações e manifesto de integridade;
- perfil clínico aprovado e protocolo versionado, template humano validado;
- exportações A1/T1, com perfil e referencial compatíveis;
- metadados históricos da revisão de carga;
- artefatos locais da Etapa 5C para auditar a separação do experimento de ML.

Após fornecer essas entradas, em uma cópia de reprodução limpa:

```bash
python3 "etapa8/a1t1_v4/executar.py" --check
python3 "etapa8/a1t1_v4/executar.py" --congelar
python3 "etapa8/a1t1_v4/executar.py" --executar
```

O congelamento ocorre após a coleta humana, antes do cálculo geométrico; não
equivale a um pré-registro prospectivo. Código e entradas são vinculados por
hash. Os comandos recusam sobrescrever congelamento ou resultados existentes;
novas entradas exigem nova versão. Não há download ou envio de dados.

## Métricas e separação do ML

As coordenadas A1/T1 são uma referência de um avaliador, sem consenso nem
verdade anatômica. Cada ponto é convertido do referencial multi5 para o STL
original e para cada normalizador congelado. Não se estimam R/t com landmarks.
Cada landmark usa os mesmos conteúdos nos métodos sem normalização, controle,
regra anatômica e multi5_rmse.

A dispersão é `sqrt(trace(cov))`, em coordenadas completas e com remoção do
centroide geométrico. São 10.000 reamostragens por conteúdo-paciente proxy,
seed 20261110, IC95% percentis e contrastes pareados contra sem normalização.
Ausências são relatadas sem imputação; n<2 não é estimável. Landmarks não são
pacientes independentes. IC condicionais às marcações e transformações fixas,
sem cobertura da confiabilidade do avaliador. Comparações exploratórias,
sem correção de multiplicidade; morfologia e pose contribuem para a dispersão.

O classificador substituto usa a divisão própria da Etapa 5C, mantendo aliases,
hashes de conteúdo e blocos de paciente proxy nas mesmas partições. Marcações
de teste não entram no treino/seleção de um detector. Se o teste já foi aberto,
a execução registra e audita os resultados existentes, sem retreino ou novas
predições. Um detector de landmarks exige desenho e configuração próprios:
treino para ajuste, validação para escolha e congelamento antes do teste.
As câmeras originais continuam PLACEHOLDER.

## Testes

```bash
python3 -m unittest discover -s "etapa8/tests" -q
```

Os testes usam dados sintéticos temporários. Uma verificação adicional de
integridade das fontes reais é ignorada quando os ativos privados não estão
disponíveis. Os testes das referências complementares constroem um perfil
artificial e não precisam do perfil clínico local. Os scripts `testar_*_no_slicer.py`
requerem execução em processo separado do Slicer; alguns precisam de cópias
locais autorizadas dos ativos e não devem acessar uma sessão humana em curso.

**Consistência não demonstra correção anatômica.** Identidade clínica não
confirmada, unidades presumidas do STL, possível influência das propostas do
template e ausência de confiabilidade medida limitam a interpretação. Os IDs
`BASE_OSSEA_*` são nomes legados de referências de superfície; não certificam
osso exposto ou segmentado. A ferramenta apoia pesquisa e julgamento humano.
