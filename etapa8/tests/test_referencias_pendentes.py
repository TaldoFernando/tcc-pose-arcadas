"""Referências ósseas pendentes: nenhum caso humano é marcado nestes testes."""
import copy,importlib,io,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE)]
from fixtures import SyntheticStudy
from e8_common import sha
import referencias_pendentes as refs
import etapa8_painel_visual as visual
LABELS=["BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA"]

class ReferenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix="e8-refs-synthetic-");self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.f=SyntheticStudy(self.root)
  # Perfil inteiramente artificial: o clone público não inclui perfis clínicos locais.
  self.profile={"schema":"etapa8.referencias_piloto.v1","escopo":"pilot","referencias":[
   {"label":label,"nome":"REFERENCIA SINTETICA","arcada":arch,"provisorio":True,
    "enabled":True,"validado":False,"propagar":False,"obrigatorio_exportacao_piloto":True,
    "permitir_marcacao_provisoria_piloto":True,"definicao_provisoria":"SOMENTE FIXTURE SINTETICA",
    "descricao_painel":description,"criterios_orientadora":{k:None for k in (*refs.CRITERIA,"aprovado_por_papel","data_validacao")},
    "observabilidade_por_ID":{"P001":{"observavel":None,"confirmado_pela_orientadora":False}}}
   for label,arch,description in [(LABELS[0],"superior","Céu da boca — exemplo sintético"),
                                 (LABELS[1],"inferior","Fundo da boca — exemplo sintético")]]}
  self.profile["perfil_base_sha256"]=sha(self.root/"landmarks_propostos.json")
  self.write()
  self.session={"ID":"P001","avaliador":"A1","sessao":"T1","phase":"pilot","definitions":copy.deepcopy(self.f.defs["landmarks"]),"exported":True}
 def write(self):(self.root/refs.PROFILE).write_text(json.dumps(self.profile))
 def enable(self,index=0):
  r=self.profile["referencias"][index]
  r.update(enabled=True,validado=True,propagar=False,permitir_marcacao_provisoria_piloto=False)
  r["criterios_orientadora"]={"estrutura_ossea_exata":"ESTRUTURA SINTETICA","local_do_clique":"LOCAL SINTETICO","vista_de_referencia":"VISTA SINTETICA","aprovado_por_papel":"orientadora","data_validacao":"2026-01-01"}
  r["observabilidade_por_ID"]["P001"].update(observavel=True,confirmado_pela_orientadora=True)
  self.write();return r
 def enable_both(self):
  self.enable(0);self.enable(1)
 def test_profile_is_provisional_enabled_for_pilot_not_validated_or_propagated(self):
  for r in self.profile["referencias"]:
   self.assertIs(r["enabled"],True);self.assertIs(r["validado"],False);self.assertIs(r["propagar"],False)
   self.assertIs(r["permitir_marcacao_provisoria_piloto"],True)
   self.assertIs(r["obrigatorio_exportacao_piloto"],True)
 def test_P001_both_visible_rows_pending_point_definition(self):
  rows=refs.linhas(self.session,self.root)
  self.assertEqual([r["label"] for r in rows],LABELS)
  self.assertTrue(all(r["habilitada"] and r["marcacao_provisoria"] and not r["validacao_clinica_confirmada"] for r in rows))
  self.assertTrue(all(r["estado"]=="Piloto: marcação provisória; definição pendente" for r in rows))
  self.assertIn("Céu da boca",rows[0]["descricao_painel"])
  self.assertIn("Fundo da boca",rows[1]["descricao_painel"])
  self.assertTrue(all(r["observabilidade_por_ID"]["P001"]["observavel"] is None for r in rows))
 def test_base_node_definitions_preserved_while_complement_is_required(self):
  original=copy.deepcopy(self.session["definitions"]);refs.estado(self.session,self.root)
  self.assertEqual(original,self.session["definitions"])
 def test_non_observable_cannot_be_clicked_even_if_flags_changed(self):
  self.enable();self.profile["referencias"][0]["observabilidade_por_ID"]["P001"]["observavel"]=False;self.write()
  with self.assertRaisesRegex(ValueError,"Não observável"):refs.posicionar(self.session,LABELS[0],[1,2,3],self.root)
 def test_each_human_criterion_required(self):
  for field in refs.CRITERIA:
   self.enable();self.profile["referencias"][0]["criterios_orientadora"][field]=None;self.write()
   self.assertFalse(refs.linhas(self.session,self.root)[0]["habilitada"])
 def test_validation_and_observability_both_required(self):
  self.enable()
  for where,key in [(self.profile["referencias"][0],"validado"),(self.profile["referencias"][0]["observabilidade_por_ID"]["P001"],"confirmado_pela_orientadora")]:
   where[key]=False;self.write();self.assertFalse(refs.linhas(self.session,self.root)[0]["habilitada"]);where[key]=True
 def test_propagation_never_allowed(self):
  r=self.enable();r["propagar"]=True;self.write()
  self.assertFalse(refs.linhas(self.session,self.root)[0]["habilitada"])
 def test_manual_position_requires_individual_confirmation(self):
  self.enable_both();refs.posicionar(self.session,LABELS[0],[1,2,3],self.root)
  with self.assertRaisesRegex(ValueError,"confirmação"):refs.preflight(self.session,self.root)
  refs.confirmar(self.session,LABELS[0],"corrigido",self.root)
  with self.assertRaisesRegex(ValueError,LABELS[1]):refs.preflight(self.session,self.root)
  refs.posicionar(self.session,LABELS[1],[4,5,6],self.root);refs.confirmar(self.session,LABELS[1],"aceito",self.root)
  refs.preflight(self.session,self.root)
  self.assertEqual(refs.estado(self.session,self.root)["points"][LABELS[0]]["position"],[1,2,3])
 def test_absence_is_null(self):
  self.enable();refs.posicionar(self.session,LABELS[0],[1,2,3],self.root);refs.confirmar(self.session,LABELS[0],"nao_visivel",self.root)
  self.assertIsNone(refs.estado(self.session,self.root)["points"][LABELS[0]]["position"])
 def test_disabled_refs_block_export_without_writing_or_fabricating_review(self):
  for r in self.profile["referencias"]:r["enabled"]=False
  self.write()
  primary=self.root/"piloto_export.json";primary.write_text('{"DADO":"SINTETICO"}')
  with self.assertRaisesRegex(ValueError,"Referência obrigatória bloqueia"):refs.preflight(self.session,self.root)
  with self.assertRaisesRegex(ValueError,"Referência obrigatória bloqueia"):refs.exportar(self.session,primary,self.root)
  self.assertFalse(refs.caminho_exportacao(self.session,self.root).exists())
  self.assertTrue(all(q["position"] is None and q["review"] is None for q in refs.estado(self.session,self.root)["points"].values()))
 def test_provisional_pilot_can_place_confirm_export_without_fabricating_approval(self):
  for label in LABELS:refs.posicionar(self.session,label,[1,2,3],self.root)
  with self.assertRaisesRegex(ValueError,"confirmação"):refs.preflight(self.session,self.root)
  for label in LABELS:refs.confirmar(self.session,label,"aceito",self.root)
  primary=self.root/"piloto_export.json";primary.write_text('{"DADO":"SINTETICO"}')
  refs.exportar(self.session,primary,self.root)
  exported=json.loads(refs.caminho_exportacao(self.session,self.root).read_text())
  for point in exported["points"]:
   self.assertTrue(point["marcacao_provisoria"]);self.assertFalse(point["validado"]);self.assertFalse(point["validacao_clinica_confirmada"])
   self.assertIsNone(point["criterios_orientadora"]["data_validacao"])
 def test_no_provisional_permission_keeps_unvalidated_reference_disabled(self):
  self.profile["referencias"][0]["permitir_marcacao_provisoria_piloto"]=False;self.write()
  self.assertFalse(refs.linhas(self.session,self.root)[0]["habilitada"])
 def test_export_requires_both_reviews_and_records_required_contract(self):
  self.enable_both();primary=self.root/"piloto_export.json";primary.write_text('{"DADO":"SINTETICO"}')
  for label in LABELS:refs.posicionar(self.session,label,[1,2,3],self.root)
  with self.assertRaisesRegex(ValueError,"confirmação"):refs.exportar(self.session,primary,self.root)
  for label in LABELS:refs.confirmar(self.session,label,"aceito",self.root)
  refs.exportar(self.session,primary,self.root)
  p=json.loads(refs.caminho_exportacao(self.session,self.root).read_text())
  self.assertEqual(len(p["points"]),2)
  self.assertEqual(p["schema"],"etapa8.referencias_obrigatorias_piloto.v2")
  self.assertEqual(p["required_labels"],LABELS)
  self.assertTrue(all(q["obrigatorio_exportacao_piloto"] is True and q["human_reviewed"] is True for q in p["points"]))
  self.assertNotEqual(refs.caminho_exportacao(self.session,self.root).parent,self.root/"marcacoes")
 def test_explicit_reviewed_absence_is_null_and_never_silently_skipped(self):
  self.enable_both()
  for label in LABELS:refs.confirmar(self.session,label,"nao_visivel",self.root)
  refs.preflight(self.session,self.root)
  self.assertTrue(all(p["position"] is None and p["review"]["status"]=="nao_visivel" for p in refs.estado(self.session,self.root)["points"].values()))
 def test_missing_profile_or_required_entry_blocks_export(self):
  (self.root/refs.PROFILE).unlink()
  with self.assertRaisesRegex(ValueError,"obrigatórias"):refs.preflight(self.session,self.root)
  self.write();self.profile["referencias"].pop();self.write()
  with self.assertRaisesRegex(ValueError,"duas referências obrigatórias"):refs.preflight(self.session,self.root)
 def test_turning_off_required_flag_is_rejected(self):
  self.profile["referencias"][0]["obrigatorio_exportacao_piloto"]=False;self.write()
  with self.assertRaisesRegex(ValueError,"duas referências obrigatórias"):refs.preflight(self.session,self.root)
 def test_main_study_and_template_unaffected(self):
  (self.root/refs.PROFILE).unlink()
  for phase in ["study","template"]:
   s=dict(self.session,phase=phase)
   self.assertEqual(refs.linhas(s,self.root),[]);self.assertIsNone(refs.estado(s,self.root));refs.preflight(s,self.root)
 def test_profile_change_after_position_rejected(self):
  self.enable();refs.posicionar(self.session,LABELS[0],[1,2,3],self.root)
  self.profile["new_revision"]="SINTETICA";self.write()
  with self.assertRaises(ValueError):refs.estado(self.session,self.root)
 def test_base_profile_change_disables_enabled_reference(self):
  self.enable();p=self.root/"landmarks_propostos.json";p.write_text(p.read_text()+" ")
  self.assertFalse(refs.linhas(self.session,self.root)[0]["habilitada"])
 def test_reopen_preserves_session_even_when_reload_fails(self):
  session={"ID":"P001","marks":object(),"dialog":None};fake=types.ModuleType("slicer_markups");fake._SESSION=session
  def fake_reload(module):
   module._SESSION=None
   return module
  with patch.dict(sys.modules,{"slicer_markups":fake}),patch.object(visual,"fechar"),patch.object(visual,"painel",return_value="PAINEL"),patch("importlib.reload",side_effect=fake_reload):
   self.assertEqual(visual.reabrir(),"PAINEL");self.assertIs(fake._SESSION,session)
  def broken(module):
   module._SESSION=None;raise RuntimeError("FALHA SINTETICA")
  with patch.dict(sys.modules,{"slicer_markups":fake}),patch.object(visual,"fechar"),patch("importlib.reload",side_effect=broken):
   with self.assertRaises(RuntimeError):visual.reabrir()
   self.assertIs(fake._SESSION,session)
if __name__=="__main__":unittest.main()
