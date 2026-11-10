"""Executar dentro do 3D Slicer. Sem rede, instalações ou anotações automáticas finais."""
from pathlib import Path
import csv,datetime,json
import numpy as np
import slicer,vtk
from e8_common import ROOT,FRAME,PRESENT,ABSENT,load,sha,safe_id,protocol,protocol_path,verify_frozen,save_csv,validate_annotation,validate_template,local_today,real_date
_SESSION=None
def _poly(path):
 r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update();out=vtk.vtkPolyData();out.DeepCopy(r.GetOutput())
 if out.GetNumberOfPoints()==0:raise ValueError('Malha vazia.')
 return out
def _combined(identifier):
 append=vtk.vtkAppendPolyData()
 for arch in ['superior','inferior']:append.AddInputData(_poly(ROOT/'assets'/identifier/f'{arch}.stl'))
 append.Update();out=vtk.vtkPolyData();out.DeepCopy(append.GetOutput());return out
def _position(node,k):
 if node.GetNthControlPointPositionStatus(k)!=slicer.vtkMRMLMarkupsNode.PositionDefined:return None
 p=[0.,0.,0.];node.GetNthControlPointPositionWorld(k,p);return p
def _fiducials(name,points,color,locked=False):
 node=slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',name);node.CreateDefaultDisplayNodes();display=node.GetDisplayNode();display.SetSelectedColor(*color);display.SetColor(*color);display.SetTextScale(1.8)
 for label,p in points:
  k=node.AddControlPoint(vtk.vtkVector3d(*(p or [0.,0.,0.])),label)
  if p is None:node.UnsetNthControlPointPosition(k)
  node.SetNthControlPointLocked(k,locked)
 node.SetLocked(locked);return node
def iniciar(identifier,avaliador='A1',sessao='T1',modo='assistida',descartar_nao_exportado=False):
 """Abre somente uma sessão. Dados de outros avaliadores não são carregados."""
 global _SESSION
 safe_id(identifier);verify_frozen();plan=load(ROOT/'plano.json')
 if avaliador not in ['A1','A2'] or sessao not in ['T1','T2'] or modo not in ['assistida','manual']:raise ValueError('Use A1/A2, T1/T2 e assistida/manual.')
 phase='template' if identifier==plan['template_ID'] else ('pilot' if identifier in plan['pilot_development_IDs'] else 'study')
 if identifier not in plan['study_IDs']+plan['pilot_development_IDs']+[plan['template_ID']]:raise ValueError('ID fora do desenho.')
 if sessao=='T2' and (phase!='study' or identifier not in plan['repeat_IDs']):raise ValueError('ID não sorteado para remarcação.')
 if sessao=='T2':
  # Só metadados de agenda; nunca carregar coordenadas T1 na remarcação.
  previous=ROOT/'listas'/f'datas_T1_{avaliador}.json'
  if not previous.exists():raise ValueError('Coordenação: execute analisar.py --check e forneça apenas os metadados de data T1 deste avaliador.')
  dates=load(previous)
  if identifier not in dates:raise ValueError('T1 revisada ainda não disponível para a coordenação.')
  elapsed=(local_today()-real_date(dates[identifier]['acquisition_date'])).days
  if elapsed<plan.get('minimum_repeat_days',14):raise ValueError('Aguardar pelo menos 14 dias desde T1. Nenhuma coordenada anterior foi carregada.')
 if _SESSION and not _SESSION.get('exported') and not descartar_nao_exportado:raise ValueError('Exporte a sessão atual ou confirme descartar_nao_exportado=True.')
 definitions=protocol(validated=phase!='pilot');definition_path=protocol_path(ROOT,validated=phase!='pilot');landmarks=[p for p in definitions['landmarks'] if p.get('enabled',True)]
 if phase=='study' and modo!=plan['annotation_mode'].split()[0]:
  raise ValueError('Desenho principal assistido; não misturar marcação manual sem novo protocolo.')
 if _SESSION and _SESSION.get('dialog'):_SESSION['dialog'].close()
 # Lê VTK diretamente: identidade numérica entre C e mundo Slicer, sem flip LPS.
 # Os rótulos R/A/S na tela NÃO certificam anatomia nem lateralidade clínica.
 for node in list(slicer.util.getNodesByClass('vtkMRMLNode')):
  if node.GetName() and node.GetName().startswith('E8_'):slicer.mrmlScene.RemoveNode(node)
 models={}
 for arch,color in [('superior',(0.88,0.84,0.72)),('inferior',(0.65,0.80,0.94))]:
  model=slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode',f'E8_{identifier}_{arch}');model.SetAndObservePolyData(_poly(ROOT/'assets'/identifier/f'{arch}.stl'));model.CreateDefaultDisplayNodes();model.GetDisplayNode().SetColor(*color);models[arch]=model
 proposed={};icp_meta={'status':'sem_template_humano'}
 if modo=='assistida' and phase!='template':
  path=ROOT/'template/template_validado.json'
  if path.exists():
   template=validate_template()
   icp=vtk.vtkIterativeClosestPointTransform();icp.SetSource(_combined(plan['template_ID']));icp.SetTarget(_combined(identifier));icp.GetLandmarkTransform().SetModeToRigidBody();icp.SetMaximumNumberOfIterations(60);icp.SetMaximumNumberOfLandmarks(2000);icp.StartByMatchingCentroidsOff();icp.CheckMeanDistanceOn();icp.SetMaximumMeanDistance(0.001);icp.Update();M=np.array([[icp.GetMatrix().GetElement(i,j) for j in range(4)] for i in range(4)])
   if not np.allclose(M[:3,:3].T@M[:3,:3],np.eye(3),atol=1e-6) or np.linalg.det(M[:3,:3])<0.999:raise ValueError('ICP não rígido próprio.')
   source={p['label']:p for p in template['points']}
   for lm in landmarks:
    p=source.get(lm['label'])
    if lm['propagar'] and p and p['status'] in PRESENT:proposed[lm['label']]=(M[:3,:3]@np.array(p['position'])+M[:3,3]).tolist()
   icp_meta={'status':'PROPOSTAS_NAO_ANATOMIA_VALIDADA','method':'VTK rigid pair ICP; 60 iterações, até 2000 landmarks de superfície, init identidade, limiar de deslocamento médio 0.001','matrix_template_to_patient':M.tolist(),'template_json_sha256':sha(path),'normalization_changed':False}
  elif phase=='study':raise ValueError('Marque e publique primeiro o template humano validado.')
 points=[(p['label'],proposed.get(p['label'])) for p in landmarks];hints=_fiducials(f'E8_{identifier}_PROPOSTAS',points,(.55,.55,.55),True);marks=_fiducials(f'E8_{identifier}_CORRIGIR',points,(1.,.65,.1),False)
 _SESSION={'ID':identifier,'avaliador':avaliador,'sessao':sessao,'phase':phase,'annotation_mode':modo,'definitions':landmarks,'models':models,'marks':marks,'hints':hints,'proposals':proposed,'icp':icp_meta,'reviews':{},'protocol_file':definition_path.name,'protocol_sha256_at_open':sha(definition_path),'exported':False}
 def changed(caller,event):
  if _SESSION and _SESSION.get('marks')==caller:_SESSION['exported']=False
 _SESSION['observer']=marks.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,changed)
 slicer.util.selectModule('Markups');slicer.modules.markups.logic().SetActiveListID(marks);slicer.util.resetThreeDViews();print('Sessão',identifier,avaliador,sessao,'aberta; cada ponto precisa de revisão humana explícita. Referencial C técnico; não confiar em R/L da tela.');return marks
def revisar(label,status):
 if not _SESSION:raise ValueError('Abra uma sessão.')
 if status not in PRESENT|ABSENT:raise ValueError('Status inválido.')
 node=_SESSION['marks'];labels=[node.GetNthControlPointLabel(k) for k in range(node.GetNumberOfControlPoints())]
 if label not in labels:raise ValueError('Landmark desconhecido.')
 k=labels.index(label);pos=_position(node,k)
 if status in PRESENT and pos is None:raise ValueError('Posicione o ponto primeiro.')
 if status in ABSENT:node.UnsetNthControlPointPosition(k);pos=None
 _SESSION['reviews'][label]={'status':status,'position':pos};_SESSION['exported']=False;print(label,status)
def painel():
 """Painel de revisão; o piloto exige também as duas referências complementares."""
 import qt
 import referencias_pendentes as refs
 if not _SESSION:raise ValueError('Abra uma sessão.')
 session=_SESSION
 antigo=session.get('dialog')
 if antigo is not None:antigo.close()
 dialog=qt.QDialog(slicer.util.mainWindow());dialog.setWindowTitle('Etapa 8 '+session['ID']);layout=qt.QVBoxLayout(dialog)
 layout.addWidget(qt.QLabel('Corrija os pontos em Markups. Confirme cada linha após inspecionar.'))
 scroll=qt.QScrollArea();scroll.setWidgetResizable(True);content=qt.QWidget();body=qt.QVBoxLayout(content);scroll.setWidget(content);layout.addWidget(scroll)
 grid=qt.QGridLayout();body.addLayout(grid)
 def safe(fn):
  try:
   if _SESSION is not session:raise ValueError('Painel de outra sessão.')
   return fn()
  except Exception as e:slicer.util.errorDisplay(str(e))
 def place_point(label):
  import etapa8_painel_visual as visual
  visual.painel();visual._aberto.posicionar(label)
 for row,p in enumerate(session['definitions']):
  label=p['label'];combo=qt.QComboBox();combo.addItems(['pendente','aceito','corrigido','ausente','nao_visivel','nao_aplicavel','lateralidade_incerta'])
  review=session['reviews'].get(label)
  if review:combo.setCurrentText(review['status'])
  place=qt.QPushButton('Posicionar 3D');place.connect('clicked()',lambda l=label:safe(lambda:place_point(l)))
  title=qt.QLabel(label+' · '+p['arcada']);title.setToolTip(p['definicao_provisoria']+'\nVista: '+p.get('vista_referencia','Conferir em múltiplas vistas.')+'\nAusência: '+p['ausencia'])
  button=qt.QPushButton('Confirmar ponto');grid.addWidget(title,row,0);grid.addWidget(place,row,1);grid.addWidget(combo,row,2);grid.addWidget(button,row,3)
  button.connect('clicked()',lambda l=label,c=combo:safe(lambda:revisar(l,str(c.currentText))))
 def place_reference(label):
  import etapa8_painel_visual as visual
  visual.painel();visual._aberto.posicionar_referencia(label)
 session['reference_widgets']=refs.adicionar_linhas(grid,session,ROOT,lambda l:safe(lambda:place_reference(l)),lambda l,v:safe(lambda:refs.confirmar(session,l,v,ROOT)))
 button=qt.QPushButton('Exportar sessão revisada');layout.addWidget(button)
 def do_export():
  exportar();slicer.util.infoDisplay('Sessão exportada. Atualize a planilha com data e arquivo.')
 button.connect('clicked()',lambda:safe(do_export));dialog.resize(850,700);dialog.show();session['dialog']=dialog;return dialog
def exportar():
 if not _SESSION:raise ValueError('Abra uma sessão.')
 s=_SESSION;verify_frozen()
 if s['marks'].GetParentTransformNode() is not None or any(m.GetParentTransformNode() is not None for m in s['models'].values()):raise ValueError('Transformação manual no modelo ou nos pontos: referencial C deixou de ser garantido.')
 from vtk.util.numpy_support import vtk_to_numpy
 for arch,model in s['models'].items():
  actual=vtk_to_numpy(model.GetPolyData().GetPoints().GetData());expected=vtk_to_numpy(_poly(ROOT/'assets'/s['ID']/f'{arch}.stl').GetPoints().GetData())
  if actual.shape!=expected.shape or not np.allclose(actual,expected,rtol=0,atol=1e-6):raise ValueError('Geometria modificada no Slicer. Use apenas a câmera para mudar a vista.')
 if sha(ROOT/s.get('protocol_file','landmarks_propostos.json'))!=s['protocol_sha256_at_open']:raise ValueError('Definições mudaram durante a sessão.')
 if s['phase']!='pilot':protocol()
 node=s['marks'];expected=[p['label'] for p in s['definitions']];actual=[node.GetNthControlPointLabel(k) for k in range(node.GetNumberOfControlPoints())]
 if actual!=expected:raise ValueError('Não renomear, reordenar, adicionar ou remover landmarks. Reabra e recoloque pontos se necessário.')
 points=[]
 for k,lm in enumerate(s['definitions']):
  label=lm['label'];review=s['reviews'].get(label);pos=_position(node,k)
  if review is None:raise ValueError('Falta revisão humana: '+label)
  old=review['position']
  if (pos is None)!=(old is None) or (pos is not None and not np.allclose(pos,old,rtol=0,atol=1e-7)):raise ValueError('Ponto mudou após revisão; confirme novamente: '+label)
  distance=None
  if pos is not None:
   locator=vtk.vtkCellLocator();locator.SetDataSet(s['models'][lm['arcada']].GetPolyData());locator.BuildLocator();closest=[0.,0.,0.];cell=vtk.mutable(0);sub=vtk.mutable(0);d2=vtk.mutable(0.);locator.FindClosestPoint(pos,closest,cell,sub,d2);distance=float(np.sqrt(float(d2)))
  points.append({'label':label,'arcada':lm['arcada'],'status':review['status'],'position':pos,'proposal_position':s['proposals'].get(label),'surface_distance_mm':distance})
 now=datetime.datetime.now(datetime.timezone.utc);obj={'schema':'etapa8.manual.v1','ID':s['ID'],'avaliador':s['avaliador'],'sessao':s['sessao'],'phase':s['phase'],'annotation_mode':s['annotation_mode'],'frame':FRAME,'slicer_numeric_world':'RAS values identical to C by direct VTK loading; anatomical directions unverified','units':'mm_assumed_from_STL','display_normalization':'multi5_rmse','human_reviewed':True,'created_utc':now.isoformat(),'acquisition_date':local_today().isoformat(),'acquisition_timezone':'America/Fortaleza','protocol_file':s.get('protocol_file','landmarks_propostos.json'),'protocol_sha256':sha(ROOT/s.get('protocol_file','landmarks_propostos.json')),'transforms_sha256':sha(ROOT/'transformacoes_congeladas.json'),'slicer_version':slicer.app.applicationVersion,'points':points,'proposal_registration':s['icp']}
 folder=ROOT/({'study':'marcacoes','pilot':'piloto_marcacoes','template':'template'}[s['phase']]);folder.mkdir(exist_ok=True);name=f"{s['ID']}_{s['avaliador']}_{s['sessao']}" if s['phase']!='template' else f"{s['ID']}_template";target=folder/(name+'.json')
 if target.exists():raise ValueError('Arquivo já existe; não sobrescrever avaliação anterior. Preserve a versão e resolva a duplicidade com a coordenação.')
 import referencias_pendentes as refs
 refs.preflight(s,ROOT)
 if s['phase']=='pilot':obj['required_pilot_references']={'profile_sha256':sha(ROOT/refs.PROFILE),'labels':list(refs.REQUIRED_LABELS),'file':refs.caminho_exportacao(s,ROOT).name,'mandatory_entries_total':len(points)+len(refs.REQUIRED_LABELS),'contains_provisional_definitions':any(r['marcacao_provisoria'] for r in refs.linhas(s,ROOT))}
 # CSV usa vazios reais para ausência; nunca coordenada zero fictícia.
 flat=[{'ID':s['ID'],'avaliador':s['avaliador'],'sessao':s['sessao'],'landmark':p['label'],'arcada':p['arcada'],'status':p['status'],'x_mm':p['position'][0] if p['position'] else None,'y_mm':p['position'][1] if p['position'] else None,'z_mm':p['position'][2] if p['position'] else None,'frame':FRAME,'surface_distance_mm':p['surface_distance_mm']} for p in points]
 csvpath=folder/(name+'.csv')
 if csvpath.exists() or (folder/(name+'.mrk.json')).exists():raise ValueError('Saída anterior existente; não sobrescrever.')
 # Markups nativo de intercâmbio, sem nomes de nó ou pacientes e com RAS explícito.
 mrk={'@schema':'https://raw.githubusercontent.com/Slicer/Slicer/main/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.0.json#','markups':[{'type':'Fiducial','coordinateSystem':'RAS','coordinateUnits':'mm','locked':True,'controlPoints':[{'id':str(k+1),'label':p['label'],'position':p['position'] or [0.,0.,0.],'positionStatus':'defined' if p['position'] else 'undefined','description':p['status']} for k,p in enumerate(points)]}]}
 validate_annotation(obj,phase=s['phase'])
 target.write_text(json.dumps(obj,indent=2));save_csv(csvpath,flat);(folder/(name+'.mrk.json')).write_text(json.dumps(mrk,indent=2));refs.exportar(s,target,ROOT);s['exported']=True;print('EXPORTADO',target.name,'sem nomes de paciente; arquivo de análise .json, não .mrk.json.');return str(target)
def publicar_template():
 """Executar por pessoa após revisar e exportar o template sob a definição final."""
 verify_frozen();protocol();plan=load(ROOT/'plano.json');source=ROOT/'template'/f"{plan['template_ID']}_template.json"
 obj=validate_annotation(load(source),phase='template')
 valid=[p['position'] for p in obj['points'] if p['status'] in PRESENT]
 if len(valid)<3:raise ValueError('Template sem pelo menos três pontos humanos presentes.')
 target=ROOT/'template/template_validado.json'
 if target.exists():raise ValueError('Template já publicado; não sobrescrever depois de iniciar o estudo.')
 obj['approved_as_template']=True;obj['approved_template_date']=local_today().isoformat()
 target.write_text(json.dumps(obj,indent=2));print('Template humano publicado; propostas continuam exigindo revisão individual.')
 return str(target)
