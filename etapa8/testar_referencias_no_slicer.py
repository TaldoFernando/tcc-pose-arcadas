"""Verifica linhas pendentes e exportação em instância isolada do Slicer.
P001 é lido somente para inspeção local. Todos os estados de revisão simulados
e arquivos de exportação ficam em diretório temporário, nunca na coleta real.
"""
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
import datetime,importlib.util,json,os,shutil,sys,tempfile,traceback
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import slicer,vtk,numpy as np
import slicer_markups as e8
import e8_common as common
import referencias_pendentes as refs
import etapa8_painel_visual as visual
OUT=ROOT/"qa/marcacao_provisoria_piloto"
LABELS=["BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA"]

@contextmanager
def isolated(root,identifier):
    created=[]
    try:
        with patch.object(e8,"ROOT",root), \
             patch.object(e8,"verify_frozen",lambda:common.verify_frozen(root)), \
             patch.object(e8,"protocol",lambda validated=True:common.protocol(root,validated)), \
             patch.object(e8,"validate_annotation",lambda obj,phase="study":common.validate_annotation(obj,root,phase=phase)):
            e8.iniciar(identifier,"A1","T1",modo="manual")
            created.extend([*e8._SESSION["models"].values(),e8._SESSION["marks"],e8._SESSION["hints"]])
            yield e8._SESSION
    finally:
        visual.fechar()
        for node in reversed(created):
            if node.GetScene() is not None:slicer.mrmlScene.RemoveNode(node)
        e8._SESSION=None

def fixture(root):
    spec=importlib.util.spec_from_file_location("e8_refs_fixture",ROOT/"tests/fixtures.py")
    f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    return f.SyntheticStudy(root)

def rows_visible(widgets):
    assert set(widgets)==set(LABELS)
    for label,w in widgets.items():
        assert label in str(w["nome"].text)
        assert "Obrigatória" in str(w["nome"].toolTip)
        assert w["row"]==16+LABELS.index(label)
        assert w["grid"].rowCount()==18
        assert w["grid"].columnCount()==4
        assert w["grid"].itemAtPosition(w["row"],0).widget() is w["cell"]
        for column,key in [(1,"posicionar"),(2,"combo"),(3,"confirmar")]:
            assert w["grid"].itemAtPosition(w["row"],column).widget() is w[key]
        assert w["grid"].itemAtPosition(15,3).widget().text=="Confirmar ponto"
        assert str(w["estado"].text)=="Piloto: marcação provisória; definição pendente"
        assert ("Céu da boca" if label==LABELS[0] else "Fundo da boca") in str(w["nome"].text)
        assert w["posicionar"].isEnabled() and w["confirmar"].isEnabled() and w["combo"].isEnabled()

def execute():
    assert e8._SESSION is None,"Não executar na sessão real em andamento."
    slicer.util.mainWindow().hide()
    hashes={p:common.sha(p) for p in (ROOT/"assets/P001").glob("*.stl")}
    with tempfile.TemporaryDirectory(prefix="e8-refs-P001-export-SIMULADO-") as tmp:
        root=Path(tmp);f=fixture(root)
        for n in ["landmarks_propostos.json","perfil_referencias_piloto.json","plano.json","transformacoes_congeladas.json"]:
            shutil.copy2(ROOT/n,root/n)
        dest=root/"assets/P001";dest.mkdir(parents=True)
        for arch in ["superior","inferior"]:shutil.copy2(ROOT/"assets/P001"/(arch+".stl"),dest/(arch+".stl"))
        with isolated(root,"P001") as s:
            count=s["marks"].GetNumberOfControlPoints();assert count==16
            standard=e8.painel();slicer.app.processEvents()
            rows_visible(s["reference_widgets"])
            areas=slicer.util.findChildren(widget=standard,className="QScrollArea")
            if areas:areas[0].ensureWidgetVisible(s["reference_widgets"][LABELS[0]]["nome"])
            slicer.app.processEvents()
            assert standard.grab().save(str(OUT/"P001_painel_padrao.png"))
            visual.painel();slicer.app.processEvents();v=visual._aberto
            rows_visible(v.referencias_widgets)
            areas=slicer.util.findChildren(widget=v.dialogo,className="QScrollArea")
            if areas:areas[0].ensureWidgetVisible(v.referencias_widgets[LABELS[0]]["nome"])
            slicer.app.processEvents()
            assert v.dialogo.grab().save(str(OUT/"P001_painel_visual.png"))
            assert s["marks"].GetNumberOfControlPoints()==count
            for lm in s["definitions"]:e8.revisar(lm["label"],"ausente")
            try:v.exportar()
            except ValueError as e:assert "confirmação individual" in str(e)
            else:raise AssertionError("Piloto incompleto foi exportado.")
            assert not list((root/"piloto_marcacoes").glob("*"))
            assert not refs.caminho_exportacao(s,root).exists()
            assert not (root/"qa/visualizacao/P001_A1_T1.json").exists()
            coordinates={}
            for label,arch in zip(LABELS,["superior","inferior"]):
                widgets=v.referencias_widgets[label]
                widgets["posicionar"].click();slicer.app.processEvents()
                assert v.alvo==("referencia",label,arch)
                canonical=list(s["models"][arch].GetPolyData().GetPoint(0));coordinates[label]=canonical
                v.clique.AddControlPoint(vtk.vtkVector3d(*visual._para_visual(canonical,v.dz[arch])))
                slicer.app.processEvents()
                point=refs.estado(s,root)["points"][label]
                np.testing.assert_allclose(point["position"],canonical,atol=1e-8)
                assert point["review"] is None
                widgets["combo"].setCurrentText("aceito");widgets["confirmar"].click();slicer.app.processEvents()
                assert point["review"]["status"]=="aceito"
                if label==LABELS[0]:
                    try:v.exportar()
                    except ValueError as e:assert LABELS[1] in str(e)
                    else:raise AssertionError("Exportou faltando a segunda referência.")
            main=json.loads(Path(v.exportar()).read_text())
            assert main["required_pilot_references"]["contains_provisional_definitions"] is True
            exported=json.loads(refs.caminho_exportacao(s,root).read_text())
            for point in exported["points"]:
                assert point["marcacao_provisoria"] is True and point["validado"] is False and point["validacao_clinica_confirmada"] is False
                assert point["criterios_orientadora"]["data_validacao"] is None
                np.testing.assert_allclose(point["position"],coordinates[point["label"]],atol=1e-8)
            # Mesmos comandos recomendados ao usuário: fechar só a cópia visual,
            # atualizar o módulo e restaurar o objeto de sessão após reload de e8.
            saved_session=e8._SESSION;saved_marks=s["marks"];saved_reviews=dict(s["reviews"])
            visual.fechar()
            importlib.reload(visual)
            visual.reabrir().hide()
            assert e8._SESSION is saved_session and e8._SESSION["marks"] is saved_marks
            assert e8._SESSION["reviews"]==saved_reviews
            for label in LABELS:
                point=refs.estado(saved_session,root)["points"][label]
                np.testing.assert_allclose(point["position"],coordinates[label],atol=1e-8)
                assert point["review"]["status"]=="aceito"
            rows_visible(visual._aberto.referencias_widgets)
            visual.fechar()
    assert all(common.sha(p)==h for p,h in hashes.items())

    # Caso positivo artificial: P897/esferas; nenhuma definição humana real é habilitada.
    with tempfile.TemporaryDirectory(prefix="e8-refs-habilitacao-SINTETICA-") as tmp:
        root=Path(tmp);f=fixture(root);folder=root/"assets/P897";folder.mkdir(parents=True)
        p=json.loads((ROOT/refs.PROFILE).read_text());p["perfil_base_sha256"]=common.sha(root/"landmarks_propostos.json")
        for lm in p["referencias"]:
            lm.update(enabled=True,validado=True,propagar=False)
            lm["criterios_orientadora"]={"estrutura_ossea_exata":"ESTRUTURA SINTETICA","local_do_clique":"PONTO SINTETICO","vista_de_referencia":"VISTA SINTETICA","aprovado_por_papel":"orientadora","data_validacao":"2026-01-01"}
            lm["observabilidade_por_ID"]["P897"]={"observavel":True,"confirmado_pela_orientadora":True,"nota":"SOMENTE FIXTURE ARTIFICIAL"}
        (root/refs.PROFILE).write_text(json.dumps(p))
        for arch,z in [("superior",2),("inferior",-2)]:
            shape=vtk.vtkSphereSource();shape.SetCenter(0,0,z);shape.Update()
            writer=vtk.vtkSTLWriter();writer.SetInputData(shape.GetOutput());writer.SetFileName(str(folder/(arch+".stl")));assert writer.Write()==1
        with isolated(root,"P897") as s:
            visual.painel();v=visual._aberto
            assert v.referencias_widgets[LABELS[0]]["posicionar"].isEnabled()
            v.posicionar_referencia(LABELS[0])
            canonical=list(s["models"]["superior"].GetPolyData().GetPoint(0))
            v.clique.AddControlPoint(vtk.vtkVector3d(*visual._para_visual(canonical,v.dz["superior"])))
            slicer.app.processEvents()
            point=refs.estado(s,root)["points"][LABELS[0]]
            np.testing.assert_allclose(point["position"],canonical,atol=1e-8);assert point["review"] is None
            try:refs.preflight(s,root)
            except ValueError:pass
            else:raise AssertionError("Faltou bloquear referência sem confirmação.")
            v.confirmar_referencia(LABELS[0],"aceito")
            assert all(e8._position(s["marks"],k) is None for k in range(s["marks"].GetNumberOfControlPoints()))
            for lm in s["definitions"]:e8.revisar(lm["label"],"ausente")
            try:v.exportar()
            except ValueError as e:assert LABELS[1] in str(e)
            else:raise AssertionError("Exportou com apenas uma referência confirmada.")
            assert not list((root/"piloto_marcacoes").glob("*"))
            v.posicionar_referencia(LABELS[1])
            lower=list(s["models"]["inferior"].GetPolyData().GetPoint(0))
            v.clique.AddControlPoint(vtk.vtkVector3d(*visual._para_visual(lower,v.dz["inferior"])))
            slicer.app.processEvents();v.confirmar_referencia(LABELS[1],"aceito")
            analytic=json.loads(Path(v.exportar()).read_text())
            assert analytic["required_pilot_references"]["labels"]==LABELS
            assert analytic["required_pilot_references"]["mandatory_entries_total"]==len(s["definitions"])+2
            supplement=json.loads(refs.caminho_exportacao(s,root).read_text())
            assert supplement["schema"]=="etapa8.referencias_obrigatorias_piloto.v2"
            assert all(point["human_reviewed"] is True and point["obrigatorio_exportacao_piloto"] is True for point in supplement["points"])
            np.testing.assert_allclose(supplement["points"][0]["position"],canonical,atol=1e-8)
            np.testing.assert_allclose(supplement["points"][1]["position"],lower,atol=1e-8)
    return {"P001_duas_linhas_obrigatorias_painel_padrao":True,"P001_duas_linhas_obrigatorias_painel_visual":True,"P001_estado_marcacao_provisoria":True,"P001_botoes_posicionar_habilitados_e_clique_testado":True,"P001_copia_temporaria_exporta_como_provisoria_sem_aprovacao_ficticia":True,"P001_exportacao_incompleta_bloqueada_sem_arquivos":True,"exportacao_com_uma_referencia_bloqueada":True,"exportacao_com_definicoes_validadas_APENAS_em_P897_sintetico":True,"perfil_real_e_STL_intactos":True,"sessao_real_acessada":False,"marcacoes_humanas_salvas":0,"capturas_painel_apenas_IDs":True,"reabertura_por_reload_preserva_sessao_pontos_e_revisoes":True}

OUT.mkdir(parents=True,exist_ok=True);code=0
try:
    result={"status":"PASS","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"Slicer":slicer.app.applicationVersion,**execute()}
except Exception:
    code=1;result={"status":"FAIL","traceback":traceback.format_exc()}
(OUT/"teste_nativo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n");print(json.dumps(result,ensure_ascii=False,indent=2))
if os.environ.get("ETAPA8_REFERENCIAS_BATCH")=="1":slicer.util.exit(code)
elif code:raise RuntimeError(result["traceback"])
