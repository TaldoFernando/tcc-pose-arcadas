"""Dados inteiramente sintéticos em pasta temporária; nunca simulam coleta real."""
import sys,json,tempfile,datetime,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analisar
from e8_common import convert_point,validate_annotation,sha
class PipelineTests(unittest.TestCase):
 def test_icc_absolute_detects_bias(self):
  x=np.arange(12.)
  self.assertAlmostEqual(float(analisar.icc_absolute(np.stack([x,x],1))),1.)
  self.assertLess(float(analisar.icc_absolute(np.stack([x,x+10],1))),.5)
  self.assertTrue(np.isnan(analisar.icc_absolute(np.zeros((12,2)))))
 def test_rigid_roundtrip_and_distance(self):
  M=np.eye(4);M[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]];M[:3,3]=[3,8,-2];raw=np.array([2.,5.,7.]);p=M[:3,:3]@raw+M[:3,3];ts={'P901':{'methods':{'multi5_rmse':M.tolist(),'nenhuma':np.eye(4).tolist()}}}
  self.assertTrue(np.allclose(convert_point(p,'P901','nenhuma',ts),raw));self.assertTrue(np.allclose(convert_point(p,'P901','multi5_rmse',ts),p))
  self.assertAlmostEqual(float(analisar.spatial_sd(np.array([[0,0,0],[2,0,0]]))),np.sqrt(2))
 def test_complete_synthetic_analysis(self):
  with tempfile.TemporaryDirectory(prefix='etapa8-synthetic-') as tmp:
   root=Path(tmp);(root/'marcacoes').mkdir();ids=[f'P{901+j}' for j in range(24)];repeat=ids[:4]+ids[8:11]+ids[16:19];definitions={'approved':True,'landmarks':[{'label':n,'enabled':True} for n in ['U1_R','L1_R','U6_R','U6_L']]}
   def save(n,v):(root/n).write_text(json.dumps(v))
   save('landmarks_propostos.json',definitions);save('plano.json',{'study_IDs':ids,'repeat_IDs':repeat});save('congelamento.json',{'files':{}});save('transformacoes_congeladas.json',{'IDs':{i:{'methods':{m:np.eye(4).tolist() for m in ['nenhuma','controle','anatomica','multi5_rmse']},'raw_geometry_centroid':[0,0,0]} for i in ids}});save('protocolo_validado.json',{'definitions_sha256':sha(root/'landmarks_propostos.json'),'plan_sha256':sha(root/'plano.json'),'code_sha256':{}});(root/'amostra_coordenacao.csv').write_text('ID,grupo\n'+'\n'.join(i+','+str(j//8+1) for j,i in enumerate(ids)))
   rng=np.random.default_rng(781);base={i:rng.normal(size=(4,3)) for i in ids}
   first=None
   for i in ids:
    for r in ['A1','A2']:
     for s in (['T1','T2'] if i in repeat else ['T1']):
      obj={'schema':'etapa8.manual.v1','human_reviewed':True,'ID':i,'avaliador':r,'sessao':s,'phase':'study','annotation_mode':'assistida','frame':'CANONICAL_STL_CARTESIAN','units':'mm_assumed_from_STL','display_normalization':'multi5_rmse','acquisition_date':'2026-01-01' if s=='T1' else '2026-01-15','protocol_sha256':sha(root/'landmarks_propostos.json'),'transforms_sha256':sha(root/'transformacoes_congeladas.json'),'points':[{'label':lm['label'],'status':'corrigido','position':(base[i][k]+rng.normal(0,.01,3)).tolist()} for k,lm in enumerate(definitions['landmarks'])]};save(f'marcacoes/{i}_{r}_{s}.json',obj);first=first or obj
   self.assertEqual(len(analisar.collect(root)[0]),68)
   old=analisar.B;analisar.B=200
   try:result=analisar.analyze(root)
   finally:analisar.B=old
   self.assertEqual(result['sessions'],68);self.assertTrue((root/'resultados/confiabilidade.csv').exists());self.assertTrue((root/'resultados/dispersao_landmarks.csv').exists())
   bad=dict(first,human_reviewed=False)
   with self.assertRaises(ValueError):validate_annotation(bad,root)
   bad=dict(first,points=[dict(p) for p in first['points']]);bad['points'][0]['status']='nao_visivel'
   with self.assertRaises(ValueError):validate_annotation(bad,root)
   bad=dict(first,points=first['points']+first['points'][:1])
   with self.assertRaises(ValueError):validate_annotation(bad,root)
if __name__=='__main__':unittest.main()
