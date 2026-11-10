"""Versionamento clínico com dados inteiramente sintéticos temporários."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE)]
from fixtures import SyntheticStudy
from e8_common import protocol,protocol_path,sha,validate_annotation,validate_template
from congelar_definicoes import freeze_definitions
import analisar,coleta

class VersionedProtocolTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix="e8-versioned-synthetic-");self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.f=SyntheticStudy(self.root)
  self.original=(self.root/"landmarks_propostos.json").read_bytes()
  (self.root/"protocolo_validado.json").unlink()
  self.final=copy.deepcopy(self.f.defs);self.final["approved_date"]="2026-01-01"
  self.final["landmarks"] += [dict(label=label,arcada=arch,enabled=True,validado=True,propagar=False,definicao_provisoria="SOMENTE REFERENCIA SINTETICA",ausencia="DADO SINTETICO INDISPONIVEL") for label,arch in [("BASE_OSSEA_MAXILA","superior"),("BASE_OSSEA_MANDIBULA","inferior")]]
  self.f.save("landmarks_validados_v2.json",self.final)
  for name in ["e8_common.py","slicer_markups.py","coleta.py","analisar.py"]:(self.root/name).write_text("# SOMENTE FIXTURE SINTETICA")
 def freeze(self):return freeze_definitions("2026-01-01",True,self.root,definitions_file="landmarks_validados_v2.json")
 def annotation(self,identifier=None,rater="A1",session="T1",phase="study"):
  obj=self.f.annotation(identifier,rater,session,phase=phase)
  obj.update(protocol_sha256=sha(self.root/"landmarks_validados_v2.json"),acquisition_date="2026-01-15" if session=="T2" else "2026-01-01")
  for label,arch in [("BASE_OSSEA_MAXILA","superior"),("BASE_OSSEA_MANDIBULA","inferior")]:obj["points"].append(dict(label=label,arcada=arch,status="aceito",position=[float((identifier or self.f.ids[0])[1:]),1.,2.]))
  return obj
 def test_v2_freeze_preserves_original_and_selects_versioned_profile(self):
  lock=self.freeze();self.assertEqual(lock["enabled_landmarks"],6)
  self.assertEqual((self.root/"landmarks_propostos.json").read_bytes(),self.original)
  self.assertEqual(len(protocol(self.root)["landmarks"]),6);self.assertEqual(len(protocol(self.root,False)["landmarks"]),4)
  self.assertEqual(protocol_path(self.root).name,"landmarks_validados_v2.json")
 def test_historical_pilot_remains_valid_under_original_hash(self):
  pilot=self.f.annotation("P897",phase="pilot");self.freeze();validate_annotation(pilot,self.root,phase="pilot")
 def test_main_requires_new_points_and_hash(self):
  self.freeze()
  with self.assertRaises(ValueError):validate_annotation(self.f.annotation(),self.root)
  obj=self.annotation();validate_annotation(obj,self.root)
  obj["points"].pop()
  with self.assertRaises(ValueError):validate_annotation(obj,self.root)
 def test_template_requires_v2_profile(self):
  self.freeze();obj=self.annotation("P900",phase="template");obj.update(approved_as_template=True,approved_template_date="2026-01-01")
  self.f.save("template/template_validado.json",obj);validate_template(self.root)
 def test_versioned_profile_is_immutable_after_freeze(self):
  self.freeze();p=self.root/"landmarks_validados_v2.json";p.write_text(p.read_text()+" ")
  with self.assertRaises(ValueError):protocol(self.root)
 def test_path_traversal_and_wrong_approval_date_rejected(self):
  with self.assertRaises(ValueError):freeze_definitions("2026-01-01",True,self.root,definitions_file="../escape.json")
  with self.assertRaises(ValueError):freeze_definitions("2026-01-02",True,self.root,definitions_file="landmarks_validados_v2.json")
  self.freeze();lock=json.loads((self.root/"protocolo_validado.json").read_text());lock["definitions_file"]="../escape.json";self.f.save("protocolo_validado.json",lock)
  with self.assertRaises(ValueError):protocol(self.root)
 def test_analysis_includes_both_references_under_versioned_profile(self):
  self.freeze();template=self.annotation("P900",phase="template");template.update(approved_as_template=True,approved_template_date="2026-01-01");self.f.save("template/template_validado.json",template)
  for identifier in self.f.ids:
   for rater in ["A1","A2"]:
    for session in (["T1","T2"] if identifier in self.f.repeat else ["T1"]):self.f.write(self.annotation(identifier,rater,session))
  self.assertTrue(coleta.readiness(self.root)[0]["ready"])
  with patch.object(analisar,"B",50):analisar.analyze(self.root)
  import csv
  with (self.root/"resultados/dispersao_landmarks.csv").open() as f:rows=list(csv.DictReader(f))
  self.assertTrue({"BASE_OSSEA_MAXILA","BASE_OSSEA_MANDIBULA"}<={r["landmark"] for r in rows})
  self.assertEqual(json.loads((self.root/"resultados/status.json").read_text())["protocol_sha256"],sha(self.root/"landmarks_validados_v2.json"))
if __name__=="__main__":unittest.main()
