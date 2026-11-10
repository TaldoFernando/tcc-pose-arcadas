"""Teste nativo: executar no Python do Slicer, com cena sem coleta em andamento.
Somente pontos/superfícies sintéticos em memória e diretório temporário.
"""
from pathlib import Path
import datetime,json,sys,tempfile
import slicer,vtk
import numpy as np
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
from slicer_markups import _fiducials,_position,_SESSION
if not hasattr(slicer,'mrmlScene'):raise RuntimeError('Executar no console Python do 3D Slicer, não em pacote homônimo do Python.')
if _SESSION and not _SESSION.get('exported'):raise RuntimeError('Exporte a coleta em andamento antes do teste sintético.')
node=None;loaded=None
try:
 node=_fiducials('E8_TESTE_SINTETICO',[('TEST_DEFINED',[10.,20.,30.]),('TEST_UNDEFINED',None)],(.8,.8,.8))
 assert np.array_equal(_position(node,0),[10,20,30]);assert _position(node,1) is None
 with tempfile.TemporaryDirectory(prefix='etapa8-slicer-synthetic-') as tmp:
  file=Path(tmp)/'somente_sintetico.mrk.json';assert slicer.util.saveNode(node,str(file))
  loaded=slicer.util.loadMarkups(str(file))
  if isinstance(loaded,tuple):loaded=loaded[-1]
  assert loaded is not None
  assert np.allclose(_position(loaded,0),[10,20,30]);assert _position(loaded,1) is None
 source=vtk.vtkSphereSource();source.SetThetaResolution(21);source.SetPhiResolution(19);source.Update()
 M=vtk.vtkTransform();M.Translate(1.,2.,3.)
 target=vtk.vtkTransformPolyDataFilter();target.SetInputData(source.GetOutput());target.SetTransform(M);target.Update()
 icp=vtk.vtkIterativeClosestPointTransform();icp.SetSource(source.GetOutput());icp.SetTarget(target.GetOutput());icp.GetLandmarkTransform().SetModeToRigidBody();icp.StartByMatchingCentroidsOn();icp.SetMaximumNumberOfIterations(60);icp.Update()
 a=np.array([[icp.GetMatrix().GetElement(i,j) for j in range(4)] for i in range(4)])
 assert np.allclose(a[:3,:3].T@a[:3,:3],np.eye(3),atol=1e-6) and np.linalg.det(a[:3,:3])>.999
 assert np.allclose(a[:3,3],[1,2,3],atol=.02)
 result={'status':'PASS','data':'SOMENTE_SINTETICO_TEMPORARIO','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Slicer':slicer.app.applicationVersion,'coordinate_identity_verified':True,'native_Markups_roundtrip_verified':True,'undefined_not_measurement':True,'rigid_ICP_verified':True,'human_annotations_created':0}
 (root/'qa').mkdir(exist_ok=True);(root/'qa/slicer_smoke_test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:
 for n in [loaded,node]:
  if n is not None:slicer.mrmlScene.RemoveNode(n)
