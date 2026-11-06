from pathlib import Path
import json,html
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,Image,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[1];cat=json.loads((ROOT/"catalogo.json").read_text())
pdfmetrics.registerFont(TTFont("EstudoSerif",str(ROOT/"reproducao/fontes_print/DejaVuSerif.ttf")))
W,H=landscape(A4);width=W-5*cm
caption=ParagraphStyle("caption",fontName="EstudoSerif",fontSize=12,leading=15,spaceAfter=14)
cell=ParagraphStyle("cell",fontName="EstudoSerif",fontSize=10,leading=13)
small=ParagraphStyle("note",fontName="EstudoSerif",fontSize=10,leading=13,spaceBefore=10)
def P(s,style=cell):return Paragraph(html.escape(str(s)),style)
flow=[]
for t in cat["tabelas"]:
 if flow:flow.append(PageBreak())
 flow.append(P(f'Tabela {t["numero"]} - {t["titulo"]}',caption))
 n=len(t["colunas"])
 if n==7:ww=[4.1,0.9,4.1,3.75,3.75,3.75,3.75]
 elif n==6:ww=[4.1,1.2,1.2,6.1,3.75,3.75] if t["numero"]==4 else [2.7,4.0,1.2,4.4,4.4,4.4]
 elif n==5:ww=[5.0,4.7,4.0,5.1,4.0]
 else:ww=[5.7,3.0,6.0,6.0]
 widths=[width*x/sum(ww) for x in ww]
 data=[[P(x) for x in t["colunas"]]]+[[P(x) for x in r] for r in t["linhas"]]
 table=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT");table.setStyle(TableStyle([("LINEABOVE",(0,0),(-1,0),.8,"black"),("LINEBELOW",(0,0),(-1,0),.5,"black"),("LINEBELOW",(0,-1),(-1,-1),.8,"black"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)]))
 flow.append(table);flow.append(P("Fonte: elaboração própria, conforme registro de afirmações.\nNota: "+t["nota"],small))
for f in cat["figuras"]:
 flow.append(PageBreak());flow.append(P(f'Figura {f["numero"]} - {f["titulo"]}',caption))
 im=Image(str(ROOT/"figuras"/(f["arquivo"]+".png")));scale=min(width/im.imageWidth,10.9*cm/im.imageHeight);im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale;im.hAlign="LEFT";flow.append(im)
 flow.append(P("Fonte: elaboração própria.\nNota: "+f["nota"],small))
def footer(c,d):
 c.setFont("EstudoSerif",9);c.drawRightString(W-2*cm,1.2*cm,str(d.page))
doc=SimpleDocTemplate(str(ROOT/"resultados_ABNT.pdf"),pagesize=(W,H),leftMargin=3*cm,rightMargin=2*cm,topMargin=2.5*cm,bottomMargin=2*cm,title="Consistência de pose e modelo substituto",author="Autoria do estudo",subject="Tabelas com IC95 e figuras com ressalvas")
doc.build(flow,onFirstPage=footer,onLaterPages=footer)
print("PDF gerado")
