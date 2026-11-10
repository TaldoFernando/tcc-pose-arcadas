"""Revisão do limite de trabalho em estudo sintético temporário."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE.parent),str(HERE)]
from fixtures import SyntheticStudy
from e8_common import sha,load,expected_sessions
spec=importlib.util.spec_from_file_location('e8_limite24',HERE.parent/'coleta24_v3/gerenciar.py');manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)

class LimitTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='e8-limit24-SOMENTE-SINTETICO-');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.f=SyntheticStudy(self.root)
  for name in ['e8_common.py','slicer_markups.py','coleta.py','analisar.py']:(self.root/name).write_text('# SOMENTE FIXTURE SINTETICA')
  lock=load(self.root/'protocolo_validado.json');lock['code_sha256']={n:sha(self.root/n) for n in ['e8_common.py','slicer_markups.py','coleta.py','analisar.py']};self.f.save('protocolo_validado.json',lock)
  self.groups={i:str(j//8+1) for j,i in enumerate(self.f.ids)};self.groups.update({'P897':'1','P898':'2','P899':'3'})
  self.destination=self.root/'revisao';self.original_plan=(self.root/'plano.json').read_bytes();self.original_lock=(self.root/'protocolo_validado.json').read_bytes()
  for i in self.f.ids[:3]:self.f.write(self.f.annotation(i))
  (self.root/'piloto_marcacoes').mkdir();(self.root/'referencias_piloto').mkdir()
  for i in ['P897','P898','P899']:
   obj=self.f.annotation(i,phase='pilot');obj['annotation_mode']='manual';self.f.save('piloto_marcacoes/'+i+'_A1_T1.json',obj)
   self.f.save('referencias_piloto/'+i+'_A1_T1.referencias.json',{'exportacao_principal_sha256':sha(self.root/'piloto_marcacoes'/f'{i}_A1_T1.json'),'points':[{'human_reviewed':True},{'human_reviewed':True}]})
 def build(self):return manager.criar(self.root,self.destination,self.groups)
 def test_24_total_with_three_pilots_and_seven_assisted_per_group(self):
  self.build();p=load(self.destination/'plano_trabalho.json');self.assertEqual(len(set(p['work_IDs'])),24);self.assertEqual(len(p['assisted_main_IDs']),21)
  self.assertTrue(all(sum(self.groups[i]==g for i in p['work_IDs'])==8 for g in ['1','2','3']))
  self.assertEqual((self.root/'plano.json').read_bytes(),self.original_plan);self.assertEqual((self.root/'protocolo_validado.json').read_bytes(),self.original_lock)
  revised=load(self.destination/'analise/plano.json');self.assertEqual(len(expected_sessions(revised)),62);self.assertEqual(revised['repeat_IDs'],self.f.repeat)
 def test_initiated_or_repeat_content_is_never_removed(self):
  plan=load(self.root/'plano.json');tasks=load(self.root/'listas/A1.json');main,removed=manager.select_ids(plan,tasks,self.groups,{self.f.ids[7]})
  self.assertIn(self.f.ids[7],main);self.assertFalse(set(removed)&set(self.f.repeat));self.assertEqual(len(removed),3)
 def test_sync_counts_pilots_without_migrating_them_to_assisted_analysis(self):
  self.build();result=manager.sync(self.root,self.destination)
  self.assertEqual(result['completed_A1_including_pilots'],6);self.assertEqual(result['remaining'],18);self.assertEqual(result['assisted_main_A1_completed'],3)
  self.assertEqual(result['main_sessions_expected'],62);self.assertEqual(result['main_sessions_found'],3);self.assertFalse(result['main_analysis_ready'])
  self.assertFalse(list((self.destination/'analise/marcacoes').glob('P897*')))
  self.assertFalse((self.destination/'analise/resultados/confiabilidade.csv').exists())
  dates=load(self.root/'listas/datas_T1_A1.json');self.assertEqual(len(dates),3);self.assertNotIn('position',json.dumps(dates))
 def test_changed_annotation_is_not_silently_overwritten(self):
  self.build();manager.sync(self.root,self.destination)
  p=self.root/'marcacoes'/f'{self.f.ids[0]}_A1_T1.json';obj=load(p);obj['points'][0]['position']=[9.,8.,7.];p.write_text(json.dumps(obj))
  with self.assertRaisesRegex(ValueError,'Fonte mudou'):manager.sync(self.root,self.destination)
if __name__=='__main__':unittest.main()
