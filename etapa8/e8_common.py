"""Contratos de marcações humanas e transformações rígidas locais."""
from pathlib import Path
import csv,datetime,hashlib,json,re
import numpy as np
ROOT=Path(__file__).resolve().parent
FRAME='CANONICAL_STL_CARTESIAN'
PRESENT={'aceito','corrigido'}
ABSENT={'ausente','nao_visivel','nao_aplicavel','lateralidade_incerta'}
def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def safe_id(identifier):
 if not re.fullmatch(r'P\d{3}',identifier):raise ValueError('Use apenas ID P001...')
 return identifier
def verify_frozen(root=ROOT):
 f=load(root/'congelamento.json')
 for path,digest in f['files'].items():
  if sha(root.parent/path)!=digest:raise ValueError('Dependência congelada alterada: '+path)
def protocol(root=ROOT,validated=True):
 d=load(root/'landmarks_propostos.json')
 if validated:
  lock=load(root/'protocolo_validado.json')
  if lock['definitions_sha256']!=sha(root/'landmarks_propostos.json'):raise ValueError('Definições mudaram após validação.')
  if lock['plan_sha256']!=sha(root/'plano.json'):raise ValueError('Desenho mudou após validação.')
  for p,h in lock['code_sha256'].items():
   if sha(root/p)!=h:raise ValueError('Código mudou após validação: '+p)
  if not d['approved']:raise ValueError('Protocolo não validado por pessoa.')
 return d
def validate_annotation(obj,root=ROOT):
 if obj.get('schema')!='etapa8.manual.v1' or not obj.get('human_reviewed'):raise ValueError('Somente marcações humanas revisadas; propostas não são dados.')
 safe_id(obj['ID'])
 if obj.get('phase')!='study':raise ValueError('Piloto/template não pertencem à análise principal.')
 if obj.get('avaliador') not in ['A1','A2'] or obj.get('sessao') not in ['T1','T2']:raise ValueError('Avaliador/sessão inválidos.')
 if obj.get('frame')!=FRAME or obj.get('display_normalization')!='multi5_rmse':raise ValueError('Referencial desconhecido; não converter RAS/LPS implicitamente.')
 if obj.get('units')!='mm_assumed_from_STL':raise ValueError('Unidade incompatível; conversão deve ser documentada antes da análise.')
 if obj.get('annotation_mode') not in ['assistida','manual']:raise ValueError('Modo de anotação inválido.')
 d=protocol(root)
 if obj.get('protocol_sha256')!=sha(root/'landmarks_propostos.json'):raise ValueError('Versão de definição incompatível.')
 if obj.get('transforms_sha256')!=sha(root/'transformacoes_congeladas.json'):raise ValueError('Transformações incompatíveis.')
 expected={p['label'] for p in d['landmarks'] if p.get('enabled',True)};points=obj['points']
 if len(points)!=len(expected) or {p['label'] for p in points}!=expected:raise ValueError('Pontos ausentes, extras ou duplicados.')
 for p in points:
  if p['status'] not in PRESENT|ABSENT:raise ValueError('Ponto não revisado: '+p['label'])
  if p['status'] in PRESENT:
   a=np.array(p['position'],float)
   if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError('Coordenada inválida.')
  elif p.get('position') is not None:raise ValueError('Ponto ausente não pode ter coordenadas.')
 return obj
def convert_point(p,patient,method,transforms):
 """C_multi -> original -> método, sem usar landmarks para estimar R/t."""
 Tm=np.array(transforms[patient]['methods']['multi5_rmse']);T=np.array(transforms[patient]['methods'][method]);x=Tm[:3,:3].T@(np.asarray(p)-Tm[:3,3]);return T[:3,:3]@x+T[:3,3]
def save_csv(path,rows):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
