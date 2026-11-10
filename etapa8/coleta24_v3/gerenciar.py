"""Revisão do limite de trabalho: 24 conteúdos incluindo 3 pilotos históricos.

A análise assistida usa 21 conteúdos. Não converte pilotos em observações V2,
não modifica o congelamento original e não escolhe a amostra por resultados.
"""
from pathlib import Path
import argparse,copy,csv,datetime,json,os,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from e8_common import load,sha,protocol,verify_frozen,validate_annotation
from congelar_definicoes import freeze_definitions


def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def copy_once(source,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():
  if sha(source)!=sha(target):raise ValueError('Fonte mudou após cópia; preservar e versionar: '+source.name)
 else:shutil.copy2(source,target)


def select_ids(plan,tasks,groups,started):
 removed=[]
 for group in ['1','2','3']:
  choices=[t['ID'] for t in tasks if t['sessao']=='T1' and str(groups[t['ID']])==group and t['ID'] not in started and t['ID'] not in plan['repeat_IDs']]
  if not choices:raise ValueError('Não há conteúdo ainda não iniciado e fora de T2 no grupo '+group)
  removed.append(choices[-1])
 main=[i for i in plan['study_IDs'] if i not in removed]
 work=plan['pilot_development_IDs']+main
 if len(set(work))!=24 or any(sum(str(groups[i])==g for i in work)!=8 for g in ['1','2','3']):raise ValueError('A revisão deve conter 24 conteúdos, oito por grupo.')
 return main,removed


def criar(root=ROOT,destination=None,groups=None):
 root=Path(root).resolve();destination=Path(destination).resolve() if destination else root/'coleta24_v3';workspace=destination/'analise'
 verify_frozen(root);protocol(root)
 if (destination/'plano_trabalho.json').exists():return destination
 plan=load(root/'plano.json');tasks=load(root/'listas/A1.json')
 if groups is None:
  with (root.parent/'etapa5/rotulos_local.csv').open() as f:groups={r['ID']:r['grupo'] for r in csv.DictReader(f)}
 started=set()
 for folder in ['marcacoes','qa/visualizacao','qa/apoio_edicao']:
  for p in (root/folder).glob('*.json'):
   if p.name.endswith('.mrk.json'):continue
   item=load(p)
   if item.get('ID'):started.add(item['ID'])
 main,removed=select_ids(plan,tasks,groups,started)
 revised=copy.deepcopy(plan);revised.update(study_IDs=main,study_contents=21,per_group=7,expected_study_sessions=62,study_source='21 conteúdos assistidos preservados da amostra original; limite de trabalho total 24 incluindo três pilotos históricos',workload_including_pilots=24,workload_per_group_including_pilots=8,sample_revision='V3_LIMIT_24_INCLUDING_PILOTS',sample_revision_authorization='Instrução direta do usuário: vou so fazer 24 ja com esses 3 pilotos.',pilot_in_main_analysis=False)
 destination.mkdir(parents=True,exist_ok=True);workspace.mkdir(parents=True,exist_ok=True)
 for folder in ['marcacoes','template','listas','resultados']:(workspace/folder).mkdir(exist_ok=True)
 oldlock=load(root/'protocolo_validado.json');definitions_file=oldlock.get('definitions_file','landmarks_propostos.json')
 for name in set(['landmarks_propostos.json',definitions_file,'transformacoes_congeladas.json',*oldlock['code_sha256']]):copy_once(root/name,workspace/name)
 save(workspace/'plano.json',revised)
 for rater in ['A1','A2']:
  original=load(root/'listas'/f'{rater}.json');filtered=[]
  for session in ['T1','T2']:
   subset=[t for t in original if t['ID'] in main and t['sessao']==session]
   for index,t in enumerate(subset,1):filtered.append(dict(t,ordem=index))
  save(workspace/'listas'/f'{rater}.json',filtered)
 with (root/'amostra_coordenacao.csv').open() as f:sample=list(csv.DictReader(f))
 with (workspace/'amostra_coordenacao.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(sample[0]));writer.writeheader();writer.writerows(r for r in sample if r['ID'] in main)
 original_files=load(root/'congelamento.json')['files'];integrity={}
 for name,digest in original_files.items():integrity[os.path.relpath(root.parent/name,workspace.parent)]=digest
 for p in [workspace/'plano.json',workspace/definitions_file,Path(__file__).resolve()]:integrity[os.path.relpath(p,workspace.parent)]=sha(p)
 save(workspace/'congelamento.json',{'files':integrity,'scope':'V3 analysis of 21 assisted contents; original geometry freeze preserved','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 lock=freeze_definitions(oldlock['approved_date'],True,workspace,definitions_file=definitions_file)
 lock.update(approval_source='Aprovação clínica e definições copiadas sem alteração do protocolo V2; revisão da quantidade autorizada pelo usuário.',sample_revision_authorized_by='usuario',source_protocol_sha256=sha(root/'protocolo_validado.json'),source_plan_sha256=sha(root/'plano.json'),sample_revision_after_collection_started=True,prospective_independent_test_claim=False)
 save(workspace/'protocolo_validado.json',lock)
 work_ids=plan['pilot_development_IDs']+main
 manifest={'version':'V3_LIMIT_24_INCLUDING_PILOTS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'work_IDs':work_ids,'work_total':24,'per_group_total':8,'historical_pilot_IDs':plan['pilot_development_IDs'],'assisted_main_IDs':main,'assisted_main_total':21,'assisted_main_per_group':7,'excluded_future_IDs':removed,'template_ID':plan['template_ID'],'template_counted_in_24':False,'repeat_IDs':plan['repeat_IDs'],'raters':plan['raters'],'selection_rule':'Último ID na ordem T1/A1 de cada grupo, entre os ainda não iniciados/exportados e não sorteados para T2. Sem consultar desempenho, erros ou coordenadas.','source_protocol_sha256':sha(root/'protocolo_validado.json'),'source_plan_sha256':sha(root/'plano.json'),'root_frozen_files_modified':False,'pilots_migrated_or_relabelled':False,'main_analysis_only_assisted':True,'limitations':['Mudança do limite solicitada após três sessões principais já coletadas; não descrever como plano original prospectivo.','Os pilotos são manuais e anteriores à V2; contam no trabalho realizado e permanecem fora da análise assistida principal.','Amostra principal reduzida de oito para sete por grupo; IC potencialmente mais imprecisos.','Nenhuma validação anatômica ou identidade clínica nova é inferida.']}
 save(destination/'plano_trabalho.json',manifest)
 for rater in ['A1','A2']:
  rows=[dict(t,phase='study',annotation_mode='assistida') for t in load(workspace/'listas'/f'{rater}.json')]
  if rater=='A1':rows=[{'ID':i,'avaliador':'A1','sessao':'T1','phase':'pilot','annotation_mode':'manual_historico','historical_already_collected':True} for i in plan['pilot_development_IDs']]+rows
  save(destination/f'lista_{rater}.json',rows)
 return destination


def sync(root=ROOT,destination=None):
 root=Path(root).resolve();destination=Path(destination).resolve() if destination else root/'coleta24_v3';workspace=destination/'analise';manifest=load(destination/'plano_trabalho.json')
 verify_frozen(root);protocol(root)
 if sha(root/'protocolo_validado.json')!=manifest['source_protocol_sha256'] or sha(root/'plano.json')!=manifest['source_plan_sha256']:raise ValueError('Fonte congelada mudou; não atualizar silenciosamente a revisão.')
 for p in (root/'template').glob('*'):
  if p.is_file():copy_once(p,workspace/'template'/p.name)
 for p in (root/'marcacoes').glob('*.json'):
  if p.name.endswith('.mrk.json'):continue
  obj=validate_annotation(load(p),root)
  if obj['ID'] not in manifest['assisted_main_IDs']:continue
  for source in [p,p.with_suffix('.csv'),p.with_suffix('.mrk.json')]:
   if source.exists():copy_once(source,workspace/'marcacoes'/source.name)
 from coleta import export_check
 report=export_check(workspace)
 # Só metadados de datas T1: o Slicer mantém os caminhos originais das agendas.
 for rater in ['A1','A2']:
  source=workspace/'listas'/f'datas_T1_{rater}.json';target=root/'listas'/source.name
  save(target,load(source))
 done=[];invalid=[]
 for i in manifest['work_IDs']:
  pilot=i in manifest['historical_pilot_IDs'];folder='piloto_marcacoes' if pilot else 'marcacoes';p=root/folder/f'{i}_A1_T1.json'
  if not p.exists():continue
  try:
   obj=validate_annotation(load(p),root,phase='pilot' if pilot else 'study')
   if pilot:
    side=load(root/'referencias_piloto'/f'{i}_A1_T1.referencias.json')
    if side['exportacao_principal_sha256']!=sha(p) or len(side['points'])!=2 or not all(q['human_reviewed'] is True for q in side['points']):raise ValueError('Referências históricas incompletas.')
   done.append(i)
  except (ValueError,FileNotFoundError) as error:invalid.append({'ID':i,'error':str(error)})
 ordered=[t['ID'] for t in load(workspace/'listas/A1.json') if t['sessao']=='T1']
 result={'completed_A1_including_pilots':len(done),'target':24,'remaining':24-len(done),'completed_IDs':done,'historical_pilots_completed':len(set(done)&set(manifest['historical_pilot_IDs'])),'assisted_main_A1_completed':len(set(done)&set(manifest['assisted_main_IDs'])),'assisted_main_target':21,'next_A1_T1':next((i for i in ordered if i not in done),None),'invalid':invalid,'main_sessions_expected':report['sessions_expected'],'main_sessions_found':report['sessions_found'],'main_analysis_ready':report['ready'],'main_blockers':report['blockers'],'template_outside_count':manifest['template_ID']}
 save(destination/'progresso.json',result);return result


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--analisar',action='store_true');a=parser.parse_args()
 destination=criar();result=sync(destination=destination)
 if a.analisar:
  from analisar import analyze
  result=analyze(destination/'analise')
 print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
