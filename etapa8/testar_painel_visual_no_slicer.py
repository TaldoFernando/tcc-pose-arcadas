"""Teste nativo do complemento, só com esferas/landmarks sintéticos temporários.

Usar uma instância separada do Slicer. Nunca testa sobre a sessão de coleta.
ETAPA8_VISUAL_BATCH=1 encerra somente o processo de teste iniciado pelo launcher.
"""
from pathlib import Path
import datetime,hashlib,importlib.util,json,os,sys,tempfile,traceback
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import slicer,vtk
import numpy as np
import slicer_markups as e8
import e8_common as common
import etapa8_painel_visual as visual
import referencias_pendentes as refs


def execute():
    if e8._SESSION is not None:
        raise RuntimeError("Há uma sessão de coleta aberta. Execute o teste em outra instância do Slicer.")
    spec=importlib.util.spec_from_file_location("e8_fixture_visual",ROOT/"tests/fixtures.py")
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    created=[];evidence={}
    if os.environ.get("ETAPA8_VISUAL_BATCH")=="1":slicer.util.mainWindow().hide()
    with tempfile.TemporaryDirectory(prefix="etapa8-visual-synthetic-") as tmp:
        root=Path(tmp);study=fixture.SyntheticStudy(root)
        profile=json.loads((ROOT/refs.PROFILE).read_text())
        profile["perfil_base_sha256"]=common.sha(root/"landmarks_propostos.json")
        for reference in profile["referencias"]:
            reference.update(enabled=True,validado=True,propagar=False)
            reference["criterios_orientadora"]={"estrutura_ossea_exata":"SUPERFICIE SINTETICA","local_do_clique":"PONTO SINTETICO","vista_de_referencia":"VISTA SINTETICA","aprovado_por_papel":"orientadora","data_validacao":"2026-01-01"}
            reference["observabilidade_por_ID"]["P897"]={"observavel":True,"confirmado_pela_orientadora":True,"nota":"SOMENTE FIXTURE TEMPORARIA"}
        (root/refs.PROFILE).write_text(json.dumps(profile))
        folder=root/"assets/P897";folder.mkdir(parents=True)
        for arch,z in [("superior",1.4),("inferior",-1.4)]:
            sphere=vtk.vtkSphereSource();sphere.SetRadius(2);sphere.SetCenter(0,0,z)
            sphere.SetThetaResolution(24);sphere.SetPhiResolution(20);sphere.Update()
            writer=vtk.vtkSTLWriter();writer.SetFileTypeToBinary()
            writer.SetFileName(str(folder/(arch+".stl")));writer.SetInputData(sphere.GetOutput())
            assert writer.Write()==1
        before={p.name:common.sha(p) for p in folder.glob("*.stl")}
        try:
            with patch.object(e8,"ROOT",root), \
                 patch.object(e8,"verify_frozen",lambda:common.verify_frozen(root)), \
                 patch.object(e8,"protocol",lambda validated=True:common.protocol(root,validated)), \
                 patch.object(e8,"validate_annotation",lambda obj,phase="study":common.validate_annotation(obj,root,phase=phase)):
                e8.iniciar("P897","A1","T1",modo="manual")
                session=e8._SESSION
                created.extend([*session["models"].values(),session["marks"],session["hints"]])
                originals={a:np.array([session["models"][a].GetPolyData().GetPoint(k)
                                     for k in range(session["models"][a].GetPolyData().GetNumberOfPoints())])
                           for a in ["superior","inferior"]}
                visibility={n.GetID():n.GetDisplayNode().GetVisibility() for n in created}
                dialog=visual.painel();dialog.hide();slicer.app.processEvents()
                vista=visual._aberto
                assert visual.painel() is dialog;dialog.hide()
                assert e8._SESSION is session and session["reviews"]=={}
                bounds={a:vista.previews[a].GetPolyData().GetBounds() for a in ["superior","inferior"]}
                assert bounds["superior"][4]-bounds["inferior"][5]>=1.-1e-7
                assert all(not n.GetDisplayNode().GetVisibility() for n in created)
                evidence["sessao_preservada_sem_reiniciar"]=True

                saved={}
                for label,arch in [("U1_R","superior"),("L1_R","inferior")]:
                    index=next(i for i,p in enumerate(session["definitions"]) if p["label"]==label)
                    vista.posicionar(label)
                    assert vista.previews[arch].GetDisplayNode().GetVisibility()
                    other="inferior" if arch=="superior" else "superior"
                    assert not vista.previews[other].GetDisplayNode().GetVisibility()
                    assert vista.clique.GetNumberOfDefinedControlPoints()==0
                    assert e8._position(session["marks"],index) is None
                    canonical=list(session["models"][arch].GetPolyData().GetPoint(0))
                    world=visual._para_visual(canonical,vista.dz[arch])
                    vista.clique.AddControlPoint(vtk.vtkVector3d(*world))
                    slicer.app.processEvents()
                    np.testing.assert_allclose(e8._position(session["marks"],index),canonical,atol=1e-8)
                    assert all(n.GetDisplayNode().GetVisibility() for n in vista.previews.values())
                    vista.combos[label].setCurrentIndex(1);vista.confirmar(label)
                    saved[label]=canonical

                # Movimento da cópia visual deve alterar só a coordenada canônica correspondente.
                i=next(i for i,p in enumerate(session["definitions"]) if p["label"]=="U1_R")
                k=vista.indices["superior"].index(i)
                canonical=list(session["models"]["superior"].GetPolyData().GetPoint(8))
                vista.pontos_visuais["superior"].SetNthControlPointPositionWorld(
                    k,*visual._para_visual(canonical,vista.dz["superior"]))
                assert "U1_R" not in session["reviews"]
                np.testing.assert_allclose(e8._position(session["marks"],i),canonical,atol=1e-8)
                vista.combos["U1_R"].setCurrentIndex(2);vista.confirmar("U1_R")
                saved["U1_R"]=canonical
                evidence["arraste_convertido_e_revisao_invalidada"]=True

                # Uma transformação manual de preview não pode contaminar a exportação.
                transform=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode","E8_TEST_VIS_TRANSFORM")
                created.append(transform)
                vista.previews["superior"].SetAndObserveTransformNodeID(transform.GetID())
                try:
                    vista._ativa()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Transform no preview não foi rejeitado.")
                vista.previews["superior"].SetAndObserveTransformNodeID(None)
                for label in ["U6_R","U6_L"]:
                    vista.combos[label].setCurrentIndex(3);vista.confirmar(label)
                for label in refs.REQUIRED_LABELS:refs.confirmar(session,label,"ausente",root)
                exported=Path(vista.exportar());obj=json.loads(exported.read_text())
                assert obj["required_pilot_references"]["labels"]==list(refs.REQUIRED_LABELS)
                evidence["referencias_obrigatorias_revisadas_APENAS_em_fixture_sintetica"]=True
                common.validate_annotation(obj,root,phase="pilot")
                for point in obj["points"]:
                    if point["label"] in saved:
                        np.testing.assert_allclose(point["position"],saved[point["label"]],atol=1e-8)
                    else:
                        assert point["position"] is None and point["status"]=="ausente"
                import csv
                with exported.with_suffix(".csv").open() as f:
                    for row in csv.DictReader(f):
                        if row["status"]=="ausente":
                            assert row["x_mm"]==row["y_mm"]==row["z_mm"]==""
                mrk=json.loads(exported.with_suffix(".mrk.json").read_text())
                assert mrk["markups"][0]["coordinateSystem"]=="RAS"
                sidecar=root/"qa/visualizacao/P897_A1_T1.json"
                assert json.loads(sidecar.read_text())["referencial_exportado"]==common.FRAME
                evidence["JSON_CSV_Markups_exportados_em_C"]=True
                evidence["ausencias_nulas_sem_origem_ficticia"]=True

                # Alterar só a folga ou fechar não deve apagar pontos/revisões/exportação.
                state=json.dumps(session["reviews"],sort_keys=True)
                visual.painel(folga=2).hide();slicer.app.processEvents()
                assert e8._SESSION is session and json.dumps(session["reviews"],sort_keys=True)==state
                visual.fechar();slicer.app.processEvents()
                assert visual._aberto is None and session["exported"]
                for arch in originals:
                    model=session["models"][arch]
                    now=np.array([model.GetPolyData().GetPoint(k) for k in range(model.GetPolyData().GetNumberOfPoints())])
                    np.testing.assert_array_equal(now,originals[arch])
                for node in [*session["models"].values(),session["marks"],session["hints"]]:
                    assert node.GetDisplayNode().GetVisibility()==visibility[node.GetID()]
                assert before=={p.name:common.sha(p) for p in folder.glob("*.stl")}
                evidence["fechamento_restaura_visibilidade_sem_perda"]=True
                evidence["STL_e_modelos_originais_intactos"]=True
                evidence["cliques_simulados_via_evento_Markups"]=True
                evidence["clique_fisico_usuario_ainda_a_conferir"]=True
                return evidence
        finally:
            visual.fechar()
            for node in reversed(created):
                if node.GetScene() is not None:slicer.mrmlScene.RemoveNode(node)
            e8._SESSION=None


code=0
try:
    details=execute()
    result={"status":"PASS","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "Slicer":slicer.app.applicationVersion,"dados":"SOMENTE_SINTETICOS_EM_DIRETORIO_TEMPORARIO",
            "sessao_real_acessada":False,"marcacoes_humanas_criadas":0,**details}
except Exception:
    code=1
    result={"status":"FAIL","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "Slicer":slicer.app.applicationVersion,"dados":"SOMENTE_SINTETICOS_EM_DIRETORIO_TEMPORARIO",
            "traceback":traceback.format_exc()}
out=ROOT/"qa/painel_visual";out.mkdir(parents=True,exist_ok=True)
(out/"teste_nativo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(result,ensure_ascii=False,indent=2))
if os.environ.get("ETAPA8_VISUAL_BATCH")=="1":slicer.util.exit(code)
elif code:raise RuntimeError(result["traceback"])
