"""Testes de contratos/estatística em diretórios temporários, sem dados reais."""
import csv,copy,datetime,json,sys,tempfile,unittest,io
from pathlib import Path
from unittest.mock import patch
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE)]
import analisar,coleta
from fixtures import SyntheticStudy
from e8_common import convert_point,validate_annotation,sha,protocol,rigid_matrix,real_date,expected_sessions
from congelar_definicoes import freeze_definitions
def read_csv(path):return list(csv.DictReader(io.StringIO(Path(path).read_text())))
class StatisticsTests(unittest.TestCase):
 def test_icc_absolute_known_bias(self):
  x=np.arange(12.)
  self.assertAlmostEqual(float(analisar.icc_absolute(np.stack([x,x],1))),1.)
  self.assertAlmostEqual(float(analisar.icc_absolute(np.stack([x,x+10],1))),26/126)
  self.assertTrue(np.isnan(analisar.icc_absolute(np.zeros((12,2)))))
 def test_negative_icc_preserved(self):
  y=np.array([[0,4],[1,3],[2,2],[3,1],[4,0]],float)
  self.assertLess(float(analisar.icc_absolute(y)),0)
 def test_bootstrap_icc_vectorization(self):
  rng=np.random.default_rng(33);y=rng.normal(size=(14,2));ix=rng.integers(14,size=(25,14))
  self.assertTrue(np.allclose(analisar.icc_absolute(y[ix]),[analisar.icc_absolute(y[k]) for k in ix],equal_nan=True))
 def test_rigid_roundtrip(self):
  M=np.eye(4);M[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]];M[:3,3]=[3,8,-2];raw=np.array([2.,5.,7.]);p=M[:3,:3]@raw+M[:3,3];ts={'P901':{'methods':{'multi5_rmse':M.tolist(),'nenhuma':np.eye(4).tolist()}}}
  np.testing.assert_allclose(convert_point(p,'P901','nenhuma',ts),raw)
  np.testing.assert_allclose(convert_point(p,'P901','multi5_rmse',ts),p)
 def test_reflection_and_scale_rejected(self):
  for v in [-1,2]:
   M=np.eye(4);M[0,0]=v
   with self.assertRaises(ValueError):rigid_matrix(M)
 def test_spatial_dispersion_known_and_vectorized(self):
  x=np.array([[0,0,0],[2,0,0]])
  self.assertAlmostEqual(float(analisar.spatial_sd(x)),np.sqrt(2))
  np.testing.assert_allclose(analisar.spatial_sd(np.stack([x,x+9])),[np.sqrt(2)]*2)
 def test_icc_insufficient_sample(self):
  self.assertTrue(np.isnan(analisar.icc_absolute(np.ones((1,2)))))
  self.assertTrue(np.isnan(analisar.icc_absolute(np.ones((4,1)))))
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='etapa8-synthetic-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.f=SyntheticStudy(self.root)
 def invalid(self,**changes):
  a=self.f.annotation();a.update(changes)
  with self.assertRaises(ValueError):validate_annotation(a,self.root)
 def test_proposals_not_data(self):
  self.invalid(human_reviewed=False);self.invalid(human_reviewed='true');self.invalid(schema='proposal')
 def test_missing_requires_null(self):
  a=self.f.annotation();a['points'][0]['status']='nao_visivel'
  with self.assertRaises(ValueError):validate_annotation(a,self.root)
  a['points'][0]['position']=None;validate_annotation(a,self.root)
 def test_invalid_position_and_pending_review(self):
  for value in [[0,1],None,[0,1,float('nan')]]:
   a=self.f.annotation();a['points'][0]['position']=value
   with self.assertRaises(ValueError):validate_annotation(a,self.root)
  a=self.f.annotation();a['points'][0]['status']='pendente'
  with self.assertRaises(ValueError):validate_annotation(a,self.root)
 def test_duplicate_labels_and_arch(self):
  a=self.f.annotation();a['points'][-1]=copy.deepcopy(a['points'][0])
  with self.assertRaises(ValueError):validate_annotation(a,self.root)
  a=self.f.annotation();a['points'][0]['arcada']='inferior'
  with self.assertRaises(ValueError):validate_annotation(a,self.root)
 def test_frame_and_hash_rejected(self):
  self.invalid(frame='LPS');self.invalid(transforms_sha256='0'*64);self.invalid(protocol_sha256='0'*64);self.invalid(display_normalization='controle')
 def test_manual_main_not_accepted_as_assisted(self):self.invalid(annotation_mode='manual')
 def test_date_checks(self):
  self.invalid(acquisition_date='2026-99-01');self.invalid(acquisition_date='2999-01-01');self.invalid(acquisition_date='2025-01-01')
  with self.assertRaises(ValueError):real_date('2026-1-1')
 def test_pilot_template_outside_main(self):
  self.invalid(phase='pilot');self.invalid(ID='P900')
 def test_changed_definition_or_unvalidated_point(self):
  self.f.defs['landmarks'][0]['validado']=False;self.f.save('landmarks_propostos.json',self.f.defs);self.f.lock()
  with self.assertRaises(ValueError):protocol(self.root)
 def test_protocol_code_hash_change(self):
  code=self.root/'code.py';code.write_text('one')
  lock=json.loads((self.root/'protocolo_validado.json').read_text());lock['code_sha256']={'code.py':sha(code)};self.f.save('protocolo_validado.json',lock);code.write_text('two')
  with self.assertRaises(ValueError):protocol(self.root)
 def test_no_approval_keeps_all_pending(self):
  (self.root/'protocolo_validado.json').unlink();report=coleta.export_check(self.root)
  self.assertFalse(report['ready']);self.assertEqual(len(report['missing']),68);self.assertEqual(report['sessions_found'],0)
  self.assertEqual(len(read_csv(self.root/'acompanhamento_atualizado.csv')),68)
  self.assertFalse((self.root/'protocolo_validado.json').exists())
 def test_duplicate_session_and_short_interval(self):
  a=self.f.annotation();self.f.write(a);self.f.write(a,'P901_A1_T1_copy.json')
  report,_=coleta.readiness(self.root);self.assertTrue(any('duplicada' in q['motivo'] for q in report['invalid_sessions_or_intervals']))
  (self.root/'marcacoes/P901_A1_T1_copy.json').unlink()
  b=self.f.annotation(s='T2');b['acquisition_date']='2026-01-14';self.f.write(b)
  report,_=coleta.readiness(self.root);self.assertTrue(any(q['tipo']=='intervalo' and q['dias']==13 for q in report['invalid_sessions_or_intervals']))
 def test_date_metadata_no_T1_coordinates(self):
  self.f.write(self.f.annotation());coleta.export_check(self.root)
  d=json.loads((self.root/'listas/datas_T1_A1.json').read_text())
  self.assertEqual(d['P901']['acquisition_date'],'2026-01-01');self.assertNotIn('position',json.dumps(d));self.assertEqual(json.loads((self.root/'listas/datas_T1_A2.json').read_text()),{})
 def test_invalid_json_reported(self):
  (self.root/'marcacoes/P901_A1_T1.json').write_text('{')
  report,_=coleta.readiness(self.root);self.assertFalse(report['ready']);self.assertEqual(len(report['invalid_sessions_or_intervals']),1)
 def test_template_checks(self):
  a=json.loads((self.root/'template/template_validado.json').read_text());a['frame']='LPS';self.f.save('template/template_validado.json',a)
  report,_=coleta.readiness(self.root);self.assertTrue(any(q['etapa']=='template_humano' for q in report['blockers']))
 def test_freeze_requires_human_and_valid_points(self):
  (self.root/'protocolo_validado.json').unlink()
  with self.assertRaises(ValueError):freeze_definitions('2026-01-01',False,self.root)
  self.f.defs['approved']=False;self.f.save('landmarks_propostos.json',self.f.defs)
  with self.assertRaises(ValueError):freeze_definitions('2026-01-01',True,self.root)
  with self.assertRaises(ValueError):freeze_definitions('2999-01-01',True,self.root)
 def test_successful_synthetic_freeze_is_immutable(self):
  (self.root/'protocolo_validado.json').unlink()
  for n in ['e8_common.py','slicer_markups.py','analisar.py','coleta.py']:(self.root/n).write_text('# SOMENTE FIXTURE SINTETICA\\n')
  result=freeze_definitions('2026-01-01',True,self.root)
  self.assertEqual(result['approved_date'],'2026-01-01');self.assertIn('coleta.py',result['code_sha256'])
  original=(self.root/'protocolo_validado.json').read_bytes()
  with self.assertRaises(ValueError):freeze_definitions('2026-01-02',True,self.root)
  self.assertEqual((self.root/'protocolo_validado.json').read_bytes(),original)
 def test_freeze_after_first_annotation_rejected(self):
  self.f.write(self.f.annotation());(self.root/'protocolo_validado.json').unlink()
  with self.assertRaises(ValueError):freeze_definitions('2026-01-01',True,self.root)
 def test_template_and_approval_both_required_for_analysis(self):
  (self.root/'template/template_validado.json').unlink()
  report,_=coleta.readiness(self.root);self.assertTrue(any(b['etapa']=='template_humano' for b in report['blockers']))
class EndToEndTests(unittest.TestCase):
 def test_complete_synthetic_analysis_and_paired_dispersion(self):
  with tempfile.TemporaryDirectory(prefix='etapa8-synthetic-') as tmp:
   root=Path(tmp);f=SyntheticStudy(root,complete=True)
   self.assertEqual(len(analisar.collect(root)[0]),68);self.assertTrue(coleta.readiness(root)[0]['ready'])
   # Ausência humana sintética: nunca imputar; mesmo subconjunto em quatro métodos.
   a=f.annotation();a['points'][0].update(status='ausente',position=None);f.write(a)
   with patch.object(analisar,'B',200):result=analisar.analyze(root)
   self.assertEqual(result['sessions'],68)
   disp=read_csv(root/'resultados/dispersao_landmarks.csv')
   cell=[q for q in disp if q['grupo']=='todos' and q['landmark']=='U1_R' and q['relatorio']=='coordenadas_completas']
   self.assertEqual({q['n_conteudos'] for q in cell},{'23'});self.assertEqual(len(cell),4)
   contrasts=read_csv(root/'resultados/dispersao_diferencas_pareadas.csv')
   self.assertTrue(all(abs(float(q['delta_desvio_mm']))<1e-12 for q in contrasts))
   self.assertEqual(len(read_csv(root/'resultados/ausencias.csv')),1)
   available=read_csv(root/'resultados/disponibilidade_por_landmark.csv')
   self.assertTrue(any(q['n_conteudos_com_ausencia']=='1' for q in available))
 def test_all_absent_is_reported_not_zero_or_imputed(self):
  with tempfile.TemporaryDirectory(prefix='etapa8-synthetic-') as tmp:
   root=Path(tmp);f=SyntheticStudy(root,complete=True)
   for path in (root/'marcacoes').glob('*.json'):
    obj=json.loads(path.read_text())
    for p in obj['points']:p.update(status='nao_aplicavel',position=None)
    path.write_text(json.dumps(obj))
   with patch.object(analisar,'B',200):analisar.analyze(root)
   disp=read_csv(root/'resultados/dispersao_landmarks.csv')
   self.assertTrue(disp);self.assertTrue(all(q['n_conteudos']=='0' and q['desvio_espacial_mm']=='' for q in disp))
   self.assertEqual(read_csv(root/'resultados/referencia_humana_T1.csv'),[])
   self.assertEqual(read_csv(root/'resultados/distancias_por_ID.csv'),[])
 def test_missing_humans_never_run_analysis(self):
  with tempfile.TemporaryDirectory(prefix='etapa8-synthetic-') as tmp:
   root=Path(tmp);f=SyntheticStudy(root)
   with self.assertRaises(ValueError):analisar.analyze(root)
   self.assertFalse((root/'resultados/confiabilidade.csv').exists())
if __name__=='__main__':unittest.main()
