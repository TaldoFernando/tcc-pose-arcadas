"""Somente dados artificiais em diretório temporário; nenhum caso real."""
import json
from pathlib import Path
import numpy as np
from e8_common import sha,FRAME
class SyntheticStudy:
 def __init__(self,root,complete=False):
  self.root=Path(root)
  for n in ['marcacoes','template','listas']:(self.root/n).mkdir()
  self.ids=[f'P{901+j}' for j in range(24)];self.repeat=self.ids[:4]+self.ids[8:11]+self.ids[16:19]
  self.defs={'approved':True,'landmarks':[{'label':n,'enabled':True,'validado':True,'arcada':'inferior' if n.startswith('L') else 'superior','definicao_provisoria':'PONTO SINTETICO SEM ANATOMIA','ausencia':'indisponível no dado sintético','propagar':True} for n in ['U1_R','L1_R','U6_R','U6_L']]}
  self.plan={'study_IDs':self.ids,'repeat_IDs':self.repeat,'pilot_development_IDs':['P897','P898','P899'],'template_ID':'P900','raters':['A1','A2'],'minimum_repeat_days':14,'annotation_mode':'assistida por template sintético','expected_study_sessions':68}
  self.save('landmarks_propostos.json',self.defs);self.save('plano.json',self.plan);self.save('congelamento.json',{'files':{}})
  self.transforms={'IDs':{i:{'methods':{m:np.eye(4).tolist() for m in ['nenhuma','controle','anatomica','multi5_rmse']},'raw_geometry_centroid':[0,0,0]} for i in self.ids+['P897','P898','P899','P900']}}
  self.save('transformacoes_congeladas.json',self.transforms);self.lock()
  (self.root/'amostra_coordenacao.csv').write_text('ID,grupo\n'+'\n'.join(i+','+str(j//8+1) for j,i in enumerate(self.ids)))
  for r in ['A1','A2']:
   tasks=[{'ID':i,'avaliador':r,'sessao':s,'ordem':j+1,'arquivo_json':f'{i}_{r}_{s}.json'} for s,ids in [('T1',self.ids),('T2',self.repeat)] for j,i in enumerate(ids)]
   self.save(f'listas/{r}.json',tasks)
  rng=np.random.default_rng(781);self.base={i:rng.normal(size=(4,3)) for i in self.ids}
  if complete:
   for i in self.ids:
    for r in ['A1','A2']:
     for s in (['T1','T2'] if i in self.repeat else ['T1']):
      self.write(self.annotation(i,r,s,noise=rng.normal(0,.01,(4,3))))
  template=self.annotation('P900','A1','T1',phase='template');template.update(approved_as_template=True,approved_template_date='2025-12-31')
  self.save('template/template_validado.json',template)
 def save(self,name,value):(self.root/name).write_text(json.dumps(value))
 def lock(self):self.save('protocolo_validado.json',{'definitions_sha256':sha(self.root/'landmarks_propostos.json'),'plan_sha256':sha(self.root/'plano.json'),'approved_date':'2025-12-31','code_sha256':{}})
 def annotation(self,i=None,r='A1',s='T1',phase='study',noise=None):
  i=i or self.ids[0];positions=self.base.get(i,np.arange(12.).reshape(4,3)) if hasattr(self,'base') else np.arange(12.).reshape(4,3)
  if noise is not None:positions=positions+noise
  return {'schema':'etapa8.manual.v1','human_reviewed':True,'ID':i,'avaliador':r,'sessao':s,'phase':phase,'annotation_mode':'manual' if phase=='template' else 'assistida','frame':FRAME,'units':'mm_assumed_from_STL','display_normalization':'multi5_rmse','acquisition_date':'2025-12-31' if phase=='template' else '2026-01-01' if s=='T1' else '2026-01-15','protocol_sha256':sha(self.root/'landmarks_propostos.json'),'transforms_sha256':sha(self.root/'transformacoes_congeladas.json'),'points':[{'label':lm['label'],'arcada':lm['arcada'],'status':'corrigido','position':positions[k].tolist()} for k,lm in enumerate(self.defs['landmarks'])]}
 def write(self,obj,name=None):self.save('marcacoes/'+(name or f"{obj['ID']}_{obj['avaliador']}_{obj['sessao']}.json"),obj)
