"""Ajuda local de edição; conserva o protocolo e os exportadores congelados.

Histórico só existe a partir de ativar(). Restaurar proposta usa a sugestão
inicial do P016, nunca uma posição humana anterior supostamente recuperada.
"""
import copy,datetime,json
from pathlib import Path

_aberto=None


def _diferentes(a,b):
 if a is None or b is None:return (a is None)!=(b is None)
 return any(abs(float(x)-float(y))>1e-7 for x,y in zip(a,b))


class _Apoio:
 def __init__(self,v):
  import qt,slicer
  from e8_common import sha
  self.qt,self.slicer,self.v=qt,slicer,v
  self.s=v.sessao;self.labels=[p['label'] for p in v.definicoes]
  if self.s['phase']!='study':raise ValueError('Este complemento é para a coleta principal assistida.')
  self.closed=False;self.busy=False;self.dragging=0;self.pending=None;self.history=[];self.observers=[]
  self.focus=None;self.original_place=v.posicionar;self.visibility=[];self.shortcuts=[]
  self.last=self.snapshot()
  moment=datetime.datetime.now(datetime.timezone.utc)
  folder=v.e8.ROOT/'qa/apoio_edicao';folder.mkdir(parents=True,exist_ok=True)
  self.audit_path=folder/(f"{self.s['ID']}_{self.s['avaliador']}_{self.s['sessao']}_"+moment.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
  self.audit={'ID':self.s['ID'],'avaliador':self.s['avaliador'],'sessao':self.s['sessao'],'frame':'CANONICAL_STL_CARTESIAN','created_utc':moment.isoformat(),'code_sha256':sha(Path(__file__)),'normalization_changed':False,'annotation_mode':self.s['annotation_mode'],'history_starts_now':True,'backup_positions':self.last,'backup_reviews':copy.deepcopy(self.s['reviews']),'template_json_sha256':self.s.get('icp',{}).get('template_json_sha256'),'actions':[]}
  self.save_audit()
  self._create_controls()
  nodes=[v.marcas,*v.pontos_visuais.values()]
  for node in nodes:
   for i in range(node.GetNumberOfControlPoints()):self.visibility.append((node,i,bool(node.GetNthControlPointVisibility(i))))
  hints=[n for n in [self.s.get('hints'),*v.propostas_visuais.values()] if n is not None]
  for node in hints:
   for i in range(node.GetNumberOfControlPoints()):self.visibility.append((node,i,bool(node.GetNthControlPointVisibility(i))))
  self.hints=hints
  for node in nodes:
   for event,callback in [(slicer.vtkMRMLMarkupsNode.PointStartInteractionEvent,self.start),(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,self.end)]:self.observers.append((node,node.AddObserver(event,callback)))
  for event in [slicer.vtkMRMLMarkupsNode.PointModifiedEvent,slicer.vtkMRMLMarkupsNode.PointPositionUndefinedEvent]:self.observers.append((v.marcas,v.marcas.AddObserver(event,self.changed)))
  def place(label):
   self.focus=label;self.choice.setCurrentText(label);self.original_place(label);self.show_focus()
  self.place_wrapper=place;v.posicionar=place
  v.dialogo.connect('finished(int)',lambda *_:self.close())
  self.show_focus()
  v.aviso.setText('Sugestões cinza ocultas. Use Posicionar 3D ou escolha um ponto para vê-lo. O histórico começa agora.')

 def ensure(self):
  if self.closed or self.v.fechado or self.v.e8._SESSION is not self.s:raise ValueError('Abra/ative o apoio na sessão atual.')
  self.v._ativa()

 def snapshot(self):return {label:self.v.e8._position(self.v.marcas,i) for i,label in enumerate(self.labels)}

 def save_audit(self):
  temporary=self.audit_path.with_suffix('.tmp');temporary.write_text(json.dumps(self.audit,ensure_ascii=False,indent=2)+'\n');temporary.replace(self.audit_path)

 def action(self,kind,**fields):
  self.audit['actions'].append({'action':kind,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**fields});self.save_audit()

 def safe(self,fn):
  try:return fn()
  except Exception as e:self.slicer.util.errorDisplay(str(e))

 def _create_controls(self):
  qt=self.qt;self.bar=qt.QWidget();grid=qt.QGridLayout(self.bar)
  self.undo_button=qt.QPushButton('Desfazer movimento');self.undo_button.setEnabled(False);self.undo_button.connect('clicked()',lambda:self.safe(self.undo));grid.addWidget(self.undo_button,0,0)
  self.only=qt.QCheckBox('Mostrar só o ponto em edição');self.only.setChecked(True);self.only.connect('toggled(bool)',lambda _:self.safe(self.show_focus));grid.addWidget(self.only,0,1)
  self.choice=qt.QComboBox();self.choice.addItems(['Selecione um ponto',*self.labels]);self.choice.connect('currentTextChanged(QString)',lambda text:self.safe(lambda:self.select(str(text))));grid.addWidget(self.choice,1,0)
  restore=qt.QPushButton('Restaurar proposta inicial do P016');restore.setToolTip('Usa a sugestão inicial do template. Não recupera uma correção humana anterior à ativação.');restore.connect('clicked()',lambda:self.safe(lambda:self.restore_proposal(str(self.choice.currentText))));grid.addWidget(restore,1,1)
  note=qt.QLabel('Histórico a partir desta ativação. Restaurar/desfazer exige confirmar o ponto novamente.');note.setWordWrap(True);grid.addWidget(note,2,0,1,2)
  self.v.dialogo.layout().addWidget(self.bar)
  for key in ['Ctrl+Z','Meta+Z']:
   shortcut=qt.QShortcut(qt.QKeySequence(key),self.v.dialogo);shortcut.setContext(qt.Qt.WidgetWithChildrenShortcut);shortcut.connect('activated()',lambda:self.safe(self.undo));self.shortcuts.append(shortcut)

 def select(self,label):
  self.ensure();self.focus=label if label in self.labels else None;self.show_focus()

 def show_focus(self):
  if self.closed or self.busy:return
  self.ensure();self.busy=True;exported=self.s['exported']
  try:
   only=self.only.isChecked()
   for i,label in enumerate(self.labels):self.v.marcas.SetNthControlPointVisibility(i,not only or label==self.focus)
   for arch,indices in self.v.indices.items():
    for k,i in enumerate(indices):self.v.pontos_visuais[arch].SetNthControlPointVisibility(k,not only or self.labels[i]==self.focus)
   for node in self.hints:
    for i in range(node.GetNumberOfControlPoints()):node.SetNthControlPointVisibility(i,False)
  finally:self.s['exported']=exported;self.busy=False

 def start(self,*_):
  if self.closed or self.busy:return
  self.finish();self.dragging+=1

 def end(self,*_):
  if self.closed or self.busy:return
  self.dragging=max(0,self.dragging-1);self.finish()

 def changed(self,*_):
  if self.closed or self.busy:return
  current=self.snapshot()
  if not any(_diferentes(current[l],self.last[l]) for l in self.labels):return
  if self.pending is None:self.pending=copy.deepcopy(self.last)
  self.qt.QTimer.singleShot(0,self.finish)

 def finish(self):
  if self.closed or self.busy or self.dragging:return
  if self.pending is not None:
   current=self.snapshot()
   if any(_diferentes(current[l],self.pending[l]) for l in self.labels):self.history.append(self.pending)
   self.last=current;self.pending=None;self.undo_button.setEnabled(bool(self.history))

 def apply(self,target):
  self.ensure();self.busy=True;changed=[]
  try:
   for i,label in enumerate(self.labels):
    if label not in target or not _diferentes(self.v.e8._position(self.v.marcas,i),target[label]):continue
    if target[label] is None:self.v.marcas.UnsetNthControlPointPosition(i)
    else:self.v.marcas.SetNthControlPointPositionWorld(i,*target[label])
    self.s['reviews'].pop(label,None);self.v.combos[label].setCurrentIndex(0);changed.append(label)
   if changed:self.s['exported']=False
   self.last=self.snapshot();self.pending=None
  finally:self.busy=False
  self.show_focus();return changed

 def undo(self):
  self.ensure();self.finish()
  if self.dragging:raise ValueError('Termine o arraste antes de desfazer.')
  if not self.history:raise ValueError('Não há movimento registrado desde a ativação. O movimento anterior não tem histórico; a proposta inicial pode ser restaurada por rótulo.')
  target=self.history.pop();changed=self.apply(target);self.undo_button.setEnabled(bool(self.history));self.action('undo',labels=changed)
  self.v.aviso.setText('Movimento desfeito: '+', '.join(changed)+'. Confira e confirme novamente.');return changed

 def restore_proposal(self,label):
  self.ensure();self.finish()
  if label not in self.s['proposals']:raise ValueError('Selecione um ponto com sugestão inicial do P016. Referências manuais não têm uma proposta para restaurar.')
  target=self.s['proposals'][label];current=self.snapshot()
  if not _diferentes(current[label],target):return []
  self.history.append(current);changed=self.apply({label:list(target)});self.undo_button.setEnabled(True);self.action('restore_initial_template_proposal',labels=changed)
  self.v.aviso.setText(label+': proposta inicial restaurada; confira e confirme novamente.');return changed

 def changed_from_proposals(self):
  self.ensure();current=self.snapshot()
  return [{'label':l,'revisado':l in self.s['reviews']} for l,p in self.s['proposals'].items() if _diferentes(current[l],p)]

 def close(self):
  global _aberto
  if self.closed:return
  self.finish();self.closed=True
  for node,tag in self.observers:
   if node.GetScene() is not None:node.RemoveObserver(tag)
  if self.v.posicionar is self.place_wrapper:self.v.posicionar=self.original_place
  self.busy=True;exported=self.s['exported']
  for node,i,visible in self.visibility:
   if node.GetScene() is not None and i<node.GetNumberOfControlPoints():node.SetNthControlPointVisibility(i,visible)
  self.s['exported']=exported
  for shortcut in self.shortcuts:shortcut.setEnabled(False)
  self.bar.hide();self.action('deactivate')
  if _aberto is self:_aberto=None


def ativar():
 global _aberto
 import etapa8_painel_visual as visual
 if _aberto is not None and not _aberto.closed and _aberto.v is visual._aberto:return _aberto
 if _aberto is not None:_aberto.close()
 if visual._aberto is None:visual.painel()
 _aberto=_Apoio(visual._aberto)
 return _aberto


def alterados():
 rows=ativar().changed_from_proposals()
 print(json.dumps(rows,ensure_ascii=False,indent=2));return rows


def restaurar_proposta(label):return ativar().restore_proposal(label)


def desfazer():return ativar().undo()
