"""Duas referências complementares obrigatórias para exportar o piloto."""
from pathlib import Path
import datetime,json
from e8_common import ROOT,load,sha,PRESENT,ABSENT,real_date
PROFILE="perfil_referencias_piloto.json"
CRITERIA=("estrutura_ossea_exata","local_do_clique","vista_de_referencia")
REQUIRED_LABELS=("BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA")

def perfil(root=ROOT):
 path=Path(root)/PROFILE
 if not path.exists():raise ValueError("Perfil das referências obrigatórias do piloto não encontrado.")
 p=load(path)
 if p.get("schema")!="etapa8.referencias_piloto.v1" or p.get("escopo")!="pilot":raise ValueError("Perfil complementar de piloto inválido.")
 labels=[r["label"] for r in p["referencias"]]
 if len(labels)!=len(set(labels)):raise ValueError("Referências duplicadas.")
 if set(labels)!=set(REQUIRED_LABELS) or any(r.get("obrigatorio_exportacao_piloto") is not True for r in p["referencias"]):raise ValueError("O piloto exige as duas referências obrigatórias: "+", ".join(REQUIRED_LABELS))
 return p

def linhas(session,root=ROOT):
 if session.get("phase")!="pilot":return []
 p=perfil(root)
 if not p:return []
 base_ok=p.get("perfil_base_sha256")==sha(Path(root)/"landmarks_propostos.json")
 rows=[]
 for source in p["referencias"]:
  r=dict(source);criteria=r.get("criterios_orientadora",{});obs=r.get("observabilidade_por_ID",{}).get(session["ID"],{})
  reason=None;clinical_reason=None
  if obs.get("observavel") is False:reason="Não observável neste modelo"
  elif not base_ok:reason="Perfil-base mudou; revisão necessária"
  elif not r.get("enabled"):reason=r.get("estado_pendente","Referência pendente de habilitação")
  elif r.get("propagar") is not False:reason="Referência exige posicionamento manual"
  if r.get("validado") is not True:clinical_reason="Definição ainda não validada"
  elif any(not isinstance(criteria.get(k),str) or not criteria[k].strip() for k in CRITERIA):clinical_reason="Faltam estrutura, local do clique ou vista de referência"
  elif criteria.get("aprovado_por_papel")!="orientadora":clinical_reason="Aprovação da orientadora pendente"
  else:
   try:real_date(criteria.get("data_validacao"),"validação da referência")
   except ValueError:clinical_reason="Data de validação pendente ou inválida"
  if clinical_reason is None and (obs.get("observavel") is not True or obs.get("confirmado_pela_orientadora") is not True):clinical_reason="Observabilidade ainda não confirmada pela orientadora"
  provisional=bool(clinical_reason and r.get("permitir_marcacao_provisoria_piloto") is True and r.get("provisorio") is True)
  if reason is None and clinical_reason and not provisional:reason=clinical_reason
  r.update(habilitada=reason is None,marcacao_provisoria=reason is None and provisional,validacao_clinica_confirmada=reason is None and clinical_reason is None,estado=reason or ("Piloto: marcação provisória; definição pendente" if provisional else "Referência validada e observável; marcar manualmente"))
  rows.append(r)
 return rows

def estado(session,root=ROOT):
 if session.get("phase")!="pilot":return None
 p=perfil(root)
 h=sha(Path(root)/PROFILE);old=session.get("reference_state")
 if old and old["profile_sha256"]!=h:
  if any(x.get("position") is not None or x.get("review") for x in old["points"].values()):raise ValueError("Perfil das referências mudou após marcação; preservar/versionar a coleta complementar.")
  old=None
 if old is None:
  old={"profile_sha256":h,"points":{r["label"]:{"position":None,"review":None} for r in p["referencias"]}}
  session["reference_state"]=old
 return old

def habilitada(session,label,root=ROOT):
 row=next((r for r in linhas(session,root) if r["label"]==label),None)
 if not row or not row["habilitada"]:raise ValueError((row or {}).get("estado","Referência fora do perfil do piloto."))
 return row

def posicionar(session,label,position,root=ROOT):
 habilitada(session,label,root)
 from math import isfinite
 if len(position)!=3 or not all(map(isfinite,position)):raise ValueError("Coordenada da referência inválida.")
 point=estado(session,root)["points"][label]
 point.update(position=[float(v) for v in position],review=None);session["exported"]=False

def confirmar(session,label,status,root=ROOT):
 habilitada(session,label,root);point=estado(session,root)["points"][label]
 if status not in PRESENT|ABSENT:raise ValueError("Selecione um estado revisado.")
 if status in PRESENT and point["position"] is None:raise ValueError("Posicione manualmente a referência primeiro.")
 if status in ABSENT:point["position"]=None
 point["review"]={"status":status,"position":None if point["position"] is None else list(point["position"])}
 session["exported"]=False

def caminho_exportacao(session,root=ROOT):
 return Path(root)/"referencias_piloto"/("{ID}_{avaliador}_{sessao}.referencias.json".format(**session))

def preflight(session,root=ROOT):
 state=estado(session,root)
 if not state:return
 if caminho_exportacao(session,root).exists():raise ValueError("Exportação das referências já existe; não sobrescrever.")
 for row in linhas(session,root):
  label=row["label"];p=state["points"][label]
  if not row["habilitada"]:raise ValueError("Referência obrigatória bloqueia a exportação: "+label+" — "+row["estado"])
  review=p["review"]
  if not review or p["position"]!=review["position"]:raise ValueError("Falta confirmação individual da referência obrigatória: "+label)
  if review["status"] not in PRESENT|ABSENT:raise ValueError("Estado de revisão inválido: "+label)
  if review["status"] in PRESENT and p["position"] is None:raise ValueError("Falta posição da referência obrigatória: "+label)
  if review["status"] in ABSENT and p["position"] is not None:raise ValueError("Ausência exige coordenada nula: "+label)

def exportar(session,primary_path,root=ROOT):
 preflight(session,root)
 state=estado(session,root)
 if not state:return
 rows=linhas(session,root)
 data={"schema":"etapa8.referencias_obrigatorias_piloto.v2","ID":session["ID"],"avaliador":session["avaliador"],"sessao":session["sessao"],"phase":"pilot","frame":"CANONICAL_STL_CARTESIAN","units":"mm_assumed_from_STL","profile_sha256":state["profile_sha256"],"exportacao_principal_sha256":sha(primary_path),"fora_da_analise_principal":True,"required_labels":list(REQUIRED_LABELS),"points":[]}
 for r in rows:
  p=state["points"][r["label"]];review=p["review"]
  data["points"].append({"label":r["label"],"nome":r["nome"],"arcada":r["arcada"],"obrigatorio_exportacao_piloto":True,"enabled":r["enabled"],"habilitada":r["habilitada"],"validado":r["validado"],"validacao_clinica_confirmada":r["validacao_clinica_confirmada"],"marcacao_provisoria":r["marcacao_provisoria"],"estado":r["estado"],"position":p["position"],"status":review["status"] if review else None,"human_reviewed":review is not None,"criterios_orientadora":r["criterios_orientadora"]})
 target=caminho_exportacao(session,root);target.parent.mkdir(exist_ok=True)
 with target.open("x") as f:json.dump(data,f,ensure_ascii=False,indent=2)

def adicionar_linhas(grid,session,root,position_callback,confirm_callback):
 import qt
 rows=linhas(session,root)
 if not rows:return {}
 widgets={};first_row=grid.rowCount()
 for i,r in enumerate(rows,first_row):
  label=r["label"]
  cell=qt.QWidget();cell_layout=qt.QVBoxLayout(cell);cell_layout.setContentsMargins(0,0,0,0);cell_layout.setSpacing(0)
  title=qt.QLabel(label+" · "+r["arcada"])
  if r.get("descricao_painel"):title.setText(str(title.text)+"\n"+r["descricao_painel"])
  title.setWordWrap(True);title.setToolTip("Obrigatória no piloto. "+r["nome"]+". "+r["definicao_provisoria"]);cell_layout.addWidget(title)
  status=qt.QLabel(r["estado"]);status.setWordWrap(True);cell_layout.addWidget(status);grid.addWidget(cell,i,0)
  button=qt.QPushButton("Posicionar 3D");button.setEnabled(r["habilitada"])
  button.setToolTip(r["definicao_provisoria"]);button.connect("clicked()",lambda l=label:position_callback(l))
  grid.addWidget(button,i,1)
  combo=qt.QComboBox();combo.addItems(["pendente","aceito","corrigido","ausente","nao_visivel","nao_aplicavel","lateralidade_incerta"]);combo.setEnabled(r["habilitada"])
  point=estado(session,root)["points"][label]
  if point["review"]:combo.setCurrentText(point["review"]["status"])
  grid.addWidget(combo,i,2)
  confirm=qt.QPushButton("Confirmar ponto");confirm.setEnabled(r["habilitada"])
  confirm.connect("clicked()",lambda l=label,c=combo:confirm_callback(l,str(c.currentText)))
  grid.addWidget(confirm,i,3)
  widgets[label]={"nome":title,"estado":status,"posicionar":button,"combo":combo,"confirmar":confirm,"cell":cell,"grid":grid,"row":i}
 return widgets
