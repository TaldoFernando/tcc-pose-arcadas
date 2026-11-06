"""Smoke test nativo para execução FUTURA no Slicer; não cria marcações humanas."""
from pathlib import Path
import json,sys
import slicer,vtk
import numpy as np
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root));from slicer_markups import _fiducials,_position
node=_fiducials('E8_TESTE_SINTETICO',[('TEST_DEFINED',[10.,20.,30.]),('TEST_UNDEFINED',None)],(.8,.8,.8))
try:
 assert np.array_equal(_position(node,0),[10,20,30]);assert _position(node,1) is None
 source=vtk.vtkSphereSource();source.SetThetaResolution(21);source.SetPhiResolution(19);source.Update();M=vtk.vtkTransform();M.Translate(1.,2.,3.);target=vtk.vtkTransformPolyDataFilter();target.SetInputData(source.GetOutput());target.SetTransform(M);target.Update();icp=vtk.vtkIterativeClosestPointTransform();icp.SetSource(source.GetOutput());icp.SetTarget(target.GetOutput());icp.GetLandmarkTransform().SetModeToRigidBody();icp.StartByMatchingCentroidsOn();icp.SetMaximumNumberOfIterations(60);icp.Update();a=np.array([[icp.GetMatrix().GetElement(i,j) for j in range(4)] for i in range(4)]);assert np.linalg.det(a[:3,:3])>.999;assert np.allclose(a[:3,3],[1,2,3],atol=.02)
 result={'status':'PASS','data':'SOMENTE_SINTETICO','Slicer':slicer.app.applicationVersion,'coordinate_identity_verified':True,'undefined_not_measurement':True,'rigid_ICP_verified':True};(root/'qa/slicer_smoke_test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:slicer.mrmlScene.RemoveNode(node)
