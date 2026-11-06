"""Documento editável com formatação acadêmica para revisão institucional."""
from pathlib import Path
import re,json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[1]
doc=Document();s=doc.sections[0];s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=Cm(3);s.left_margin=Cm(3);s.right_margin=Cm(2);s.bottom_margin=Cm(2)
for name in ["Normal","Title","Heading 1","Heading 2"]:
 st=doc.styles[name];st.font.name="Times New Roman";st.font.color.rgb=RGBColor(0,0,0);st.font.size=Pt(12)
n=doc.styles["Normal"].paragraph_format;n.line_spacing=1.5;n.space_after=Pt(0);n.first_line_indent=Cm(1.25);n.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
for name in ["Heading 1","Heading 2"]:
 p=doc.styles[name].paragraph_format;p.first_line_indent=Cm(0);p.space_before=Pt(12);p.space_after=Pt(6);p.keep_with_next=True;p.line_spacing=1.5
 doc.styles[name].font.bold=True
st=doc.styles["Title"];st.font.bold=True;st.font.size=Pt(14);st.paragraph_format.first_line_indent=Cm(0);st.paragraph_format.space_after=Pt(18);st.paragraph_format.line_spacing=1.2
for block in (ROOT/"metodologia.md").read_text().split("\n\n"):
 block=block.strip()
 if not block:continue
 if block.startswith("# "):doc.add_paragraph(block[2:],style="Title")
 elif block.startswith("## "):doc.add_paragraph(block[3:],style="Heading 1")
 else:doc.add_paragraph(block.replace("\n"," "))
# Numeração de página discreta para o rascunho, sem dados pessoais de autoria.
p=s.header.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.RIGHT;p.paragraph_format.first_line_indent=Cm(0)
fld=OxmlElement("w:fldSimple");fld.set(qn("w:instr"),"PAGE");p._p.append(fld)
doc.core_properties.author="";doc.core_properties.last_modified_by="";doc.core_properties.title="Metodologia da análise de consistência de pose";doc.core_properties.subject="Consistência geométrica e modelo substituto";doc.core_properties.keywords="";doc.core_properties.comments=""
for el in list(doc.styles.element.iter()):
 if el.tag==qn("w:pBdr"):el.getparent().remove(el)
for name in ["Normal","Title","Heading 1","Heading 2"]:
 st=doc.styles[name];rf=st.element.get_or_add_rPr().get_or_add_rFonts()
 for key in ["asciiTheme","hAnsiTheme","eastAsiaTheme","cstheme"]:
  rf.attrib.pop(qn("w:"+key),None)
 for key in ["ascii","hAnsi","eastAsia","cs"]:rf.set(qn("w:"+key),"Times New Roman")
doc.save(ROOT/"metodologia.docx")
print("DOCX criado")
