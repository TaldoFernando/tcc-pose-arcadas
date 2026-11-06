"""Documento editável local; todas as definições anatômicas são propostas."""
from pathlib import Path
import json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parent;plan=json.load(open(ROOT/'plano.json'));defs=json.load(open(ROOT/'landmarks_propostos.json'))['landmarks'];doc=Document();s=doc.sections[0];s.page_height=Cm(29.7);s.page_width=Cm(21);s.top_margin=s.bottom_margin=Cm(1.8);s.left_margin=s.right_margin=Cm(2.)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
 st=doc.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0);st.font.size=Pt(10.5 if name=='Normal' else (22 if name=='Title' else 14 if name=='Heading 1' else 11.5));st.paragraph_format.space_after=Pt(6)
doc.styles['Normal'].paragraph_format.line_spacing=1.08
doc.core_properties.title='Protocolo de marcação manual dos moldes';doc.core_properties.author='Equipe de pesquisa';doc.core_properties.subject='Etapa 8 proposta para validação humana'
footer=s.footer.paragraphs[0];footer.alignment=2;r=footer.add_run('Etapa 8  |  Proposta não validada  |  ');r.font.size=Pt(8);field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
markdown=[]
def title(text):doc.add_paragraph(text,'Title');markdown.append('# '+text)
def head(text):doc.add_paragraph(text,'Heading 1');markdown.append('\n## '+text)
def sub(text):doc.add_paragraph(text,'Heading 2');markdown.append('\n### '+text)
def para(text):doc.add_paragraph(text);markdown.append('\n'+text)
def bullet(text):doc.add_paragraph(text,'List Bullet');markdown.append('- '+text)
def page():doc.add_page_break()
def table(headers,rows,widths):
 t=doc.add_table(rows=1,cols=len(headers));t.autofit=False
 for j,(text,w) in enumerate(zip(headers,widths)):t.columns[j].width=Cm(w);t.rows[0].cells[j].text=text
 for row in rows:
  cells=t.add_row().cells
  for c,text in zip(cells,row):c.text=str(text)
 for n,row in enumerate(t.rows):
  for j,c in enumerate(row.cells):
   c.width=Cm(widths[j]);pr=c._tc.get_or_add_tcPr();shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'183D56' if n==0 else ('F1F5F8' if n%2 else 'FFFFFF'));pr.append(shade);borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
   pr.append(borders)
   for p in c.paragraphs:
    p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
    for r in p.runs:r.font.size=Pt(9.5);r.font.bold=n==0;r.font.color.rgb=RGBColor.from_string('FFFFFF' if n==0 else '000000')
  trPr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trPr.append(cant)
 rep=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(rep)
 markdown.extend(['\n| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in r)+' |' for r in rows])
title('Protocolo de marcação manual dos moldes')
doc.add_paragraph('Etapa 8   Proposta para revisão da orientadora','Subtitle')
para('Este protocolo organiza a marcação humana de landmarks em pares STL e a avaliação da consistência de três normalizadores já congelados. As definições abaixo são operacionais e provisórias. Nenhum ponto foi marcado por este agente; propostas por ICP não são verdade anatômica nem substituem a revisão por pessoas.')
head('Desenho da coleta')
table(['Elemento','Definição'],[['Amostra principal','24 conteúdos únicos do teste original, 8 em cada grupo'],['Avaliadores','A1 e A2, independentes e cegos às correções do outro'],['Repetição','10 conteúdos, ambos avaliadores, após pelo menos 14 dias'],['Estratos da repetição','4 do grupo 1, 3 do grupo 2 e 3 do grupo 3'],['Piloto','3 conteúdos do desenvolvimento, um por grupo; fora da análise principal'],['Template humano','P016, do desenvolvimento, fora da amostra principal'],['Carga prevista','48 sessões T1 e 20 sessões T2, total 68'],['Sorteio','Seed 20261108, por conteúdo; aliases não são novos pacientes']],[4.,13.])
para('Os grupos servem à estratificação e não entram na normalização ou na propagação. P021/P039 foram excluídos da elegibilidade por conflito de grupo em conteúdo idêntico. Os IDs sorteados, a ordem por avaliador e a lista de repetição estão no plano e na planilha da coordenação. Não se justifica poder estatístico com esta amostra exploratória.')
head('Condições para iniciar o teste')
para('Validar definições e lateralidade no piloto; transcrever as definições finais para landmarks_propostos.json; congelar a versão por confirmação humana; marcar e publicar o template humano; só então abrir os IDs do teste. Os normalizadores anteriores nunca são alterados com essas marcações.')
page();head('Landmarks dentários propostos')
para('R e L significam direita e esquerda clínicas do paciente. O código FDI identifica o dente permanente. A orientação lateral dos STL não foi certificada; os rótulos R e L da tela do Slicer não bastam. Se a lateralidade não puder ser estabelecida, registrar lateralidade_incerta. Não substituir um dente permanente ausente por um decíduo ou vizinho.')
rows=[]
for lm in defs[:12]:
 code=lm['definicao_provisoria'].split(':')[0].replace('Dente FDI ','');label=lm['label'];short='Ponto médio da borda incisal visível' if '1_' in label else 'Ápice da cúspide do canino' if '3_' in label else 'Ápice da cúspide mesiovestibular do primeiro molar';rows.append([label,code,short])
table(['Landmark','FDI','Localização operacional provisória'],rows,[3.,2.,12.])
sub('Regras para bordas e cúspides')
para('A borda incisal é a aresta entre as superfícies vestibular e lingual/palatina; marcar seu ponto médio mesiodistal, não o centro da face vestibular. Em cúspides, marcar o ápice anatômico visível, não o ponto mais alto no eixo global. Desgaste, restauração, artefato ou anatomia sem ápice único devem ser avaliados pela orientadora e podem exigir nao_visivel. Não estimar pontos ocultos ou inexistentes.')
sub('Alinhamento e relação entre arcadas')
para('Molares, caninos e incisivos fornecem referências distribuídas nas duas arcadas para comparar a dispersão após normalização. Os pares U1_R/L1_R e U1_L/L1_L permitem um proxy de relação anteroposterior. A projeção no eixo anterior canônico ainda não é uma medida clínica validada de overjet. A articulação original é preservada; a marcação não corrige uma oclusão inadequada.')
page();head('Landmarks exploratórios da fissura')
para('Esta família é condicional. Só é proposta para fissura unilateral aberta com segmento maior e menor e margens visíveis. Grupos 1, 2 e 3 não permitem inferir topologia, lado, cirurgia ou existência de uma abertura. Não marcar uma cicatriz ou abertura imaginada como se fosse a margem da fissura.')
table(['Landmark','Proposta a substituir por definição validada'],[['F_A_MAIOR','Margem do segmento maior no limite anterior visível da descontinuidade'],['F_A_MENOR','Margem do segmento menor na seção anterior homóloga'],['F_P_MAIOR','Margem do segmento maior no limite posterior visível da mesma descontinuidade'],['F_P_MENOR','Margem do segmento menor na seção posterior homóloga']],[4.,13.])
para('A seção anatômica anterior e posterior precisa ser definida pela orientadora antes da coleta. As expressões “limite visível” e “seção homóloga” não constituem, sozinhas, definição validada. Se a definição não for adequada à dentição ou aos moldes disponíveis, desabilitar esta família no protocolo, antes do teste. Esses quatro pontos não são propagados automaticamente.')
sub('Ausências e revisão')
para('Cada ponto deve terminar com aceito ou corrigido, ou com um motivo de ausência: ausente, nao_visivel, nao_aplicavel ou lateralidade_incerta. As posições ausentes são nulas no JSON analítico e vazias no CSV; não usar zero ou coordenada média para preenchê-las. Se uma coordenada for movida depois da confirmação, confirmar a revisão novamente.')
sub('Aplicabilidade das referências')
para('A referência candidata de Ruellas et al. 2016 identificada trata de um referencial comum em imagens craniofaciais por CBCT; seus landmarks ósseos não estão disponíveis em STL dentários isolados. Botticelli et al. 2019 estuda modelos de lactentes com fissura unilateral. A transferência das definições para esta dentição e amostra exige revisão da orientadora. Nenhuma definição deste documento é apresentada como transcrição validada desses artigos.')
page();head('Marcação no 3D Slicer')
para('O Slicer não foi encontrado neste computador. Antes de coletar, executar testar_no_slicer.py no Slicer instalado, com dados sintéticos, e guardar o resultado da compatibilidade. O script principal usa VTK e Markups nativos; não instala pacotes nem envia dados à rede.')
sub('Preparação humana')
bullet('Abrir o console Python no Slicer. Adicionar a pasta etapa8 ao sys.path e importar slicer_markups como e8. Não carregar STL originais de forma independente.')
bullet('Usar iniciar no ID de piloto da lista. Revisar as definições no desenvolvimento. A coordenação atualiza o JSON, marca approved e validado como true para definições habilitadas e executa congelar_definicoes.py com confirmação humana e data real.')
bullet('Abrir P016 em modo manual, marcar e revisar os landmarks, exportar e executar publicar_template. Template só é válido se marcado sob a mesma definição congelada.')
sub('Sessão de cada avaliador')
bullet('Receber apenas a própria lista A1 ou A2, sem grupos; seguir a ordem sorteada. Iniciar um ID de cada vez. A lista CORRIGIR contém os pontos editáveis; PROPOSTAS é cinza e bloqueada.')
bullet('Inspecionar cada landmark em mais de uma vista 3D. Ocultar a arcada oposta quando necessário. No módulo Markups, selecionar a linha e posicionar ou arrastar o ponto sobre a superfície correta. Não renomear, remover ou reordenar os rótulos.')
bullet('Chamar painel para confirmar o estado de cada ponto. Conferir a definição e a superfície antes de aceitar uma proposta que não precisou ser movida. Propostas de fissura permanecem indefinidas.')
bullet('Exportar a sessão revisada. Não sobrescrever versões anteriores. Registrar a data real e conferir o arquivo na planilha. Repetir T2 depois de pelo menos 14 dias, sem visualizar as correções T1 ou as do outro avaliador.')
sub('Exemplo de console')
for line in ['import sys; sys.path.insert(0, "/caminho/local/etapa8")','import slicer_markups as e8','e8.iniciar("P016", "A1", "T1", modo="manual")','e8.painel()','e8.publicar_template()  # depois de exportar e validar o template']:
 p=doc.add_paragraph();r=p.add_run(line);r.font.name='Courier New';r.font.size=Pt(8.5);markdown.append('    '+line)
para('Trocar P016 pelo ID principal para a coleta assistida. Cada sessão exporta JSON analítico, CSV e .mrk.json de intercâmbio do Slicer, somente com IDs. Os arquivos analíticos ficam em marcacoes; piloto e template ficam separados. O modo principal é assistido: o ICC medirá este fluxo, com possível efeito de ancoragem pelas propostas comuns.')
page();head('Análises preparadas para após a coleta')
sub('Verificação e confiabilidade')
para('analisar.py --check verifica disponibilidade; analisar.py só executa a análise principal após validação humana, 68 sessões completas e intervalos válidos. Propostas, arquivos .mrk.json, template e piloto são excluídos. Pontos não visíveis não são imputados. Mistura de modos assistido/manual, duplicação de sessão, mudança de definição ou alteração de normalizador bloqueiam a execução.')
para('Interavaliador: comparar A1 e A2 em T1. Intra-avaliador: comparar T1 e T2 separadamente para A1 e A2 nos dez conteúdos repetidos. Para cada landmark, calcular a média das distâncias euclidianas 3D entre marcações, em mm presumidos. As distâncias não são erro contra verdade anatômica e são invariantes a uma transformação rígida comum do mesmo paciente.')
para('Calcular ICC de concordância absoluta e medida única, ICC(A,1), por coordenada C1, C2 e C3, e para medidas escalares disponíveis. Inter: modelo bidirecional aleatório, equivalente a ICC(2,1). Intra: modelo bidirecional misto com sessões fixas, mantendo concordância absoluta; não usar ICC(3,1) de consistência. Valores negativos são preservados; variância degenerada produz não estimável. Reportar n e IC95%.')
sub('Dispersão entre pacientes')
para('A referência humana por landmark é a média das duas marcações T1, quando ambas existem; não é ground truth absoluta. Converter do referencial multi5 para o STL original pela transformação inversa e reaplicar cada transformação congelada: nenhuma, controle, anatômica e multi5_rmse. Nenhum R ou t é estimado a partir dos landmarks.')
para('Reportar, por landmark e grupo, o desvio espacial em mm como raiz da soma das variâncias amostrais das três coordenadas, sqrt(trace(cov)). Usar os mesmos conteúdos completos em todos os métodos e diferenças pareadas contra nenhuma normalização. Não aplicar Procrustes, escala ou alinhamento adicional por landmarks.')
para('Duas leituras são produzidas: coordenadas completas e uma análise secundária com o centroide geométrico do par removido de todos os métodos, inclusive o original. A segunda controla a translação sem usar os landmarks e não muda os normalizadores. Dispersão residual contém morfologia e pose, portanto não demonstra correção anatômica.')
sub('Intervalos e pequenas amostras')
para('Bootstrap percentil com 10.000 reamostragens de conteúdos, dentro de cada estrato, mantendo avaliadores, sessões e landmarks emparelhados. Não empilhar pontos como pacientes independentes. ICC por grupo na repetição terá apenas três ou quatro conteúdos e deve ser tratado como exploratório; reportar instabilidade e quantidade de reamostragens válidas. O proxy de overjet não valida oclusão clínica.')
page();head('Controles de integridade e próximos passos')
para('Todos os assets são cópias locais do par normalizado pela variante multi5_rmse congelada. O carregamento VTK direto mantém identidade numérica entre o referencial cartesiano C e o mundo do Slicer, sem conversão implícita LPS/RAS. Os nomes anatômicos dos eixos na tela não certificam orientação clínica. JSON e CSV guardam C explicitamente; não misturar arquivos exportados por outra convenção sem conversão documentada.')
para('A coordenação mantém separada a tabela privada ID para pasta já existente. Nenhum nome de paciente entra nos arquivos desta etapa. Conservar as fontes e marcações independentes, sem “melhorar” manualmente o alinhamento do par. Manter uma só transformação rígida para as duas arcadas; o ICP de propostas transforma pontos do template e não modifica os modelos ou as regras de normalização.')
para('Depois de concluir a análise humana, pode-se planejar detector multi-view com mapas de calor. Esse treinamento não foi iniciado. Exigirá definição congelada, visibilidade por vista, câmeras próprias registradas, projeção/reconstrução 3D verificável e validação cruzada agrupada por conteúdo. Erro em pixels não deve ser apresentado como erro em mm sem reconstrução 3D e comparação com a referência humana independente.')
head('Referências para conferência')
for text in [
 'Ruellas ACO et al. Common 3-dimensional coordinate system for assessment of directional changes. Am J Orthod Dentofacial Orthop. 2016. DOI 10.1016/j.ajodo.2015.10.021. Referência candidata a confirmar com a orientadora; contexto craniofacial por CBCT. https://pmc.ncbi.nlm.nih.gov/articles/PMC4959834/',
 'Botticelli S et al. Novel 3-D Analysis for the Assessment of Cleft Dimensions on Digital Models of Infants With Unilateral Cleft Lip and Palate. Cleft Palate Craniofac J. 2019;56:127–133. DOI 10.1177/1055665618770795. Contexto de lactentes; extrapolação exige validação. https://journals.sagepub.com/doi/10.1177/1055665618770795',
 'Koo TK, Li MY. A Guideline of Selecting and Reporting Intraclass Correlation Coefficients for Reliability Research. 2016. DOI 10.1016/j.jcm.2016.02.012. Conferir também a errata. https://pmc.ncbi.nlm.nih.gov/articles/PMC4913118/',
 '3D Slicer. Markups e sistemas de coordenadas. Documentação oficial consultada em 6 de novembro de 2026. https://slicer.readthedocs.io/en/latest/user_guide/modules/markups.html  e https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html'
]:para(text)
para('Validação humana das definições e da aplicabilidade: pendente. Template humano validado: pendente. Coleta principal e análise de pacientes: pendentes. Não declarar alinhamento anatomicamente correto nem conclusões sobre o Goslon AI.')
for element in list(doc.element.xpath('.//w:pBdr'))+list(doc.styles.element.xpath('.//w:pBdr')):
 element.getparent().remove(element)
out=ROOT/'protocolo_marcacao.docx';doc.save(out);(ROOT/'PROTOCOLO.md').write_text('\n'.join(markdown)+'\n');print(out.name)
