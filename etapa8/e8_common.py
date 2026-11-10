"""Contratos locais: revisão humana, identidade de conteúdo e referenciais congelados."""
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from functools import lru_cache
import csv,datetime,hashlib,json,re
import numpy as np
ROOT=Path(__file__).resolve().parent
FRAME='CANONICAL_STL_CARTESIAN'
PRESENT={'aceito','corrigido'}
ABSENT={'ausente','nao_visivel','nao_aplicavel','lateralidade_incerta'}
TIMEZONE='America/Fortaleza'
def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
@lru_cache(maxsize=1)
def study_timezone():
 # O Python empacotado do Slicer pode não incluir TZPATH/tzdata.
 # Ler o TZif já instalado no sistema, sem rede nem offset fixo presumido.
 try:return ZoneInfo(TIMEZONE)
 except ZoneInfoNotFoundError:
  for base in [Path('/usr/share/zoneinfo'),Path('/var/db/timezone/zoneinfo')]:
   try:
    with (base/TIMEZONE).open('rb') as f:return ZoneInfo.from_file(f,key=TIMEZONE)
   except (OSError,ValueError):continue
  raise ValueError('Base de fuso America/Fortaleza indisponível; não exportar com uma data presumida.')
def local_today():return datetime.datetime.now(study_timezone()).date()
def real_date(value,field='data',today=None):
 try:
  if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError()
  result=datetime.date.fromisoformat(value)
 except (TypeError,ValueError):raise ValueError(field+': use uma data real AAAA-MM-DD.')
 if result>(today or local_today()):raise ValueError(field+': data futura não é observação humana.')
 return result
def safe_id(identifier):
 if not isinstance(identifier,str) or not re.fullmatch(r'P\d{3}',identifier):raise ValueError('Use apenas ID P001...')
 return identifier
def expected_sessions(plan):
 ids=plan['study_IDs'];repeat=plan['repeat_IDs'];raters=plan.get('raters',['A1','A2'])
 if len(ids)!=len(set(ids)) or len(repeat)!=len(set(repeat)) or not set(repeat)<=set(ids):raise ValueError('Desenho com conteúdos duplicados ou remarcações fora do estudo.')
 if raters!=['A1','A2']:raise ValueError('O desenho exige A1 e A2.')
 for i in ids+repeat:safe_id(i)
 excluded=set(plan.get('pilot_development_IDs',[]))|{plan.get('template_ID')}
 if set(ids)&excluded:raise ValueError('Piloto/template não pertencem à amostra principal.')
 return {(i,r,'T1') for i in ids for r in raters}|{(i,r,'T2') for i in repeat for r in raters}
def verify_frozen(root=ROOT):
 root=Path(root);f=load(root/'congelamento.json')
 for path,digest in f['files'].items():
  if sha(root.parent/path)!=digest:raise ValueError('Dependência congelada alterada: '+path)
def protocol_path(root=ROOT,validated=True):
 root=Path(root)
 name=load(root/'protocolo_validado.json').get('definitions_file','landmarks_propostos.json') if validated else 'landmarks_propostos.json'
 if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.json'):raise ValueError('Arquivo de definições deve estar na pasta da Etapa 8.')
 return root/name
def protocol(root=ROOT,validated=True):
 root=Path(root);path=protocol_path(root,validated);d=load(path)
 labels=[p['label'] for p in d['landmarks'] if p.get('enabled',True)]
 if not labels or len(labels)!=len(set(labels)):raise ValueError('Definições habilitadas vazias ou duplicadas.')
 if validated:
  lock=load(root/'protocolo_validado.json')
  if lock['definitions_sha256']!=sha(path):raise ValueError('Definições mudaram após validação.')
  if lock['plan_sha256']!=sha(root/'plano.json'):raise ValueError('Desenho mudou após validação.')
  for p,h in lock['code_sha256'].items():
   if sha(root/p)!=h:raise ValueError('Código mudou após validação: '+p)
  if d.get('approved') is not True or any(p.get('validado') is not True for p in d['landmarks'] if p.get('enabled',True)):raise ValueError('Definições habilitadas não validadas por pessoa.')
  real_date(lock.get('approved_date'),'data de aprovação')
 return d
def validate_annotation(obj,root=ROOT,phase='study',today=None):
 root=Path(root)
 if obj.get('schema')!='etapa8.manual.v1' or obj.get('human_reviewed') is not True:raise ValueError('Somente marcações humanas revisadas; propostas não são dados.')
 safe_id(obj.get('ID'))
 if obj.get('phase')!=phase:raise ValueError('Fase incompatível; piloto/template não pertencem à análise principal.')
 if obj.get('avaliador') not in ['A1','A2'] or obj.get('sessao') not in ['T1','T2']:raise ValueError('Avaliador/sessão inválidos.')
 if obj.get('frame')!=FRAME or obj.get('display_normalization')!='multi5_rmse':raise ValueError('Referencial desconhecido; não converter RAS/LPS implicitamente.')
 if obj.get('units')!='mm_assumed_from_STL':raise ValueError('Unidade incompatível; conversão deve ser documentada antes da análise.')
 if obj.get('annotation_mode') not in ['assistida','manual']:raise ValueError('Modo de anotação inválido.')
 d=protocol(root,validated=phase!='pilot')
 if obj.get('protocol_sha256')!=sha(protocol_path(root,validated=phase!='pilot')):raise ValueError('Versão de definição incompatível.')
 if obj.get('transforms_sha256')!=sha(root/'transformacoes_congeladas.json'):raise ValueError('Transformações incompatíveis.')
 acquired=real_date(obj.get('acquisition_date'),'data de aquisição',today)
 plan=load(root/'plano.json')
 if phase=='study':
  if (obj['ID'],obj['avaliador'],obj['sessao']) not in expected_sessions(plan):raise ValueError('Sessão fora do desenho.')
  required=plan.get('annotation_mode','assistida').split()[0]
  if obj['annotation_mode']!=required:raise ValueError('Modo de coleta diverge do desenho congelado.')
 if phase=='template' and (obj['ID']!=plan['template_ID'] or obj['annotation_mode']!='manual' or obj['sessao']!='T1'):raise ValueError('Template deve ser marcado manualmente no ID do plano.')
 if phase!='pilot':
  approved=real_date(load(root/'protocolo_validado.json')['approved_date'],'data de aprovação',today)
  if acquired<approved:raise ValueError('Marcação anterior à aprovação das definições.')
 definitions={p['label']:p for p in d['landmarks'] if p.get('enabled',True)}
 points=obj.get('points')
 if not isinstance(points,list) or len(points)!=len(definitions) or {p.get('label') for p in points}!=set(definitions):raise ValueError('Pontos ausentes, extras ou duplicados.')
 for p in points:
  lm=definitions[p['label']]
  if lm.get('arcada') and p.get('arcada')!=lm['arcada']:raise ValueError('Arcada incompatível: '+p['label'])
  if p.get('status') not in PRESENT|ABSENT:raise ValueError('Ponto não revisado: '+p['label'])
  if p['status'] in PRESENT:
   try:a=np.array(p.get('position'),float)
   except (TypeError,ValueError):raise ValueError('Coordenada inválida.')
   if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError('Coordenada inválida.')
  elif p.get('position') is not None:raise ValueError('Ponto ausente não pode ter coordenadas.')
 return obj
def validate_template(root=ROOT):
 root=Path(root);verify_frozen(root);protocol(root)
 obj=validate_annotation(load(root/'template/template_validado.json'),root,phase='template')
 if obj.get('approved_as_template') is not True:raise ValueError('Template aguarda validação humana explícita.')
 if obj.get('approved_template_date'):
  approved=real_date(obj['approved_template_date'],'validação do template')
  if approved<real_date(obj['acquisition_date']):raise ValueError('Validação do template anterior à marcação.')
 if len([p for p in obj['points'] if p['status'] in PRESENT])<3:raise ValueError('Template sem pelo menos três pontos humanos presentes.')
 return obj
def rigid_matrix(value):
 T=np.asarray(value,float)
 if T.shape!=(4,4) or not np.isfinite(T).all() or not np.allclose(T[3],[0,0,0,1],atol=1e-8) or not np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-7) or not np.isclose(np.linalg.det(T[:3,:3]),1,atol=1e-7):raise ValueError('Transformação deve ser rígida própria, em SO(3), sem escala/espelhamento.')
 return T
def convert_point(p,patient,method,transforms):
 """C_multi -> original -> método, sem usar landmarks para estimar R/t."""
 Tm=rigid_matrix(transforms[patient]['methods']['multi5_rmse']);T=rigid_matrix(transforms[patient]['methods'][method]);x=Tm[:3,:3].T@(np.asarray(p)-Tm[:3,3]);return T[:3,:3]@x+T[:3,3]
def save_csv(path,rows,fieldnames=None):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if not rows and fieldnames is None:raise ValueError('Informe colunas para tabela vazia.')
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fieldnames or list(rows[0]));w.writeheader();w.writerows(rows)
