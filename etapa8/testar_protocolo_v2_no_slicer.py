"""Integração V2 em cópias temporárias; jamais cria/coleta marcações humanas reais."""
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
import csv,datetime,json,os,shutil,sys,tempfile,traceback
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import slicer,vtk,numpy as np
import e8_common as common
import slicer_markups as e8
import etapa8_painel_visual as visual
from congelar_definicoes import freeze_definitions
OUT=ROOT/"qa/consolidacao_protocolo_20261110"

@contextmanager
def isolated(root):
 try:
  with patch.object(e8,"ROOT",root),patch.object(e8,"verify_frozen",lambda:common.verify_frozen(root)),patch.object(e8,"protocol",lambda validated=True:common.protocol(root,validated)),patch.object(e8,"validate_template",lambda:common.validate_template(root)),patch.object(e8,"validate_annotation",lambda obj,phase="study":common.validate_annotation(obj,root,phase=phase)):
   yield
 finally:
  visual.fechar()
  if e8._SESSION and e8._SESSION.get("dialog") is not None:e8._SESSION["dialog"].close()
  e8._SESSION=None
  for node in list(slicer.util.getNodesByClass("vtkMRMLNode")):
   if node.GetName() and node.GetName().startswith("E8_"):slicer.mrmlScene.RemoveNode(node)

def execute():
 assert e8._SESSION is None,"Execute em outro processo; preserve a sessão humana."
 slicer.util.mainWindow().hide()
 before={p:common.sha(p) for p in (ROOT/"assets/P016").glob("*.stl")}
 with tempfile.TemporaryDirectory(prefix="e8-v2-template-SIMULADO-") as tmp:
  root=Path(tmp)
  for name in ["plano.json","landmarks_propostos.json","landmarks_validados_v2.json","transformacoes_congeladas.json","e8_common.py","slicer_markups.py","coleta.py","analisar.py","etapa8_painel_visual.py","referencias_pendentes.py","congelar_definicoes.py"]:shutil.copy2(ROOT/name,root/name)
  for identifier in ["P016","P012"]:
   folder=root/"assets"/identifier;folder.mkdir(parents=True)
   for arch in ["superior","inferior"]:shutil.copy2(ROOT/"assets"/identifier/(arch+".stl"),folder/(arch+".stl"))
  (root/"congelamento.json").write_text(json.dumps({"files":{str(p.relative_to(root.parent)):common.sha(p) for p in (root/"assets").rglob("*.stl")}}))
  freeze_definitions("2026-11-10",True,root,definitions_file="landmarks_validados_v2.json")
  with isolated(root):
   e8.iniciar("P016","A1","T1",modo="manual");session=e8._SESSION
   assert len(session["definitions"])==18 and session["marks"].GetNumberOfControlPoints()==18
   assert session["protocol_file"]=="landmarks_validados_v2.json"
   assert session["protocol_sha256_at_open"]==common.sha(root/"landmarks_validados_v2.json")
   assert session["marks"].GetNumberOfDefinedControlPoints()==0
   standard=e8.painel();slicer.app.processEvents();assert session["reference_widgets"]=={}
   standard.grab().save(str(OUT/"P016_painel_padrao_18.png"))
   visual.painel();slicer.app.processEvents();vista=visual._aberto
   assert len(vista.combos)==18 and vista.referencias_widgets=={}
   areas=slicer.util.findChildren(widget=vista.dialogo,className="QScrollArea")
   if areas:areas[0].verticalScrollBar().setValue(areas[0].verticalScrollBar().maximum)
   slicer.app.processEvents();vista.dialogo.grab().save(str(OUT/"P016_painel_visual_18.png"))
   assert all(not session["definitions"][k]["propagar"] for k in [16,17])
   placed={}
   for label in ["U1_R","L1_R","U3_R","BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA"]:
    lm=next(lm for lm in session["definitions"] if lm["label"]==label)
    vista.posicionar(label);point=list(session["models"][lm["arcada"]].GetPolyData().GetPoint(0));placed[label]=point
    vista.clique.AddControlPoint(vtk.vtkVector3d(*visual._para_visual(point,vista.dz[lm["arcada"]])))
    slicer.app.processEvents()
    vista.combos[label].setCurrentText("aceito");vista.confirmar(label)
   for label in set(vista.combos)-set(placed):vista.combos[label].setCurrentText("ausente");vista.confirmar(label)
   obj=json.loads(Path(vista.exportar()).read_text());common.validate_annotation(obj,root,phase="template")
   assert len(obj["points"])==18 and "required_pilot_references" not in obj
   for point in obj["points"]:
    if point["label"] in placed:np.testing.assert_allclose(point["position"],placed[point["label"]],atol=1e-8)
   with (root/"template/P016_template.csv").open() as f:assert len(list(csv.DictReader(f)))==18
   mrk=json.loads((root/"template/P016_template.mrk.json").read_text());assert len(mrk["markups"][0]["controlPoints"])==18
   e8.publicar_template();common.validate_template(root)
   e8.iniciar("P012","A1","T1",modo="assistida");study=e8._SESSION
   assert len(study["definitions"])==18
   assert {"U1_R","L1_R","U3_R"}<=set(study["proposals"])
   assert not {"BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA"}&set(study["proposals"])
   visual.painel();assert len(visual._aberto.combos)==18
 assert all(common.sha(p)==h for p,h in before.items())
 return {"template_18_entradas":True,"nenhuma_coordenada_inicial_template":True,"paineis_lista_unica_18":True,"JSON_CSV_Markups_18_verificados":True,"coordenadas_canonicas_verificadas":True,"estudo_recebe_18":True,"duas_bases_exigem_marcacao_manual_sem_ICP":True,"dados":"SOMENTE_SIMULADOS_EM_COPIAS_TEMPORARIAS","marcacoes_humanas_criadas":0,"sessao_real_acessada":False,"template_real_criado":False}

OUT.mkdir(parents=True,exist_ok=True)
try:
 result={"status":"PASS","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"Slicer":slicer.app.applicationVersion,**execute()};code=0
except Exception:
 result={"status":"FAIL","traceback":traceback.format_exc()};code=1
(OUT/"teste_nativo_v2.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n");print(json.dumps(result,ensure_ascii=False,indent=2))
if os.environ.get("ETAPA8_V2_BATCH")=="1":slicer.util.exit(code)
elif code:raise RuntimeError(result["traceback"])
