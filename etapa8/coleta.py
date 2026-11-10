"""Auditoria e acompanhamento da coordenação; nunca cria aprovações ou coordenadas."""
from pathlib import Path
import collections,datetime,json,re
from e8_common import ROOT,load,sha,protocol,verify_frozen,validate_annotation,validate_template,expected_sessions,real_date,save_csv,rigid_matrix
def scan_sessions(root=ROOT):
 root=Path(root);plan=load(root/'plano.json');expected=expected_sessions(plan);found={};issues=[];seen=collections.defaultdict(int)
 for index,path in enumerate(sorted((root/'marcacoes').glob('*.json'))):
  if path.name.endswith('.mrk.json'):continue
  key=None
  try:
   obj=load(path);key=(obj.get('ID'),obj.get('avaliador'),obj.get('sessao'))
   if key not in expected:raise ValueError('Sessão fora do desenho principal.')
   seen[key]+=1
   if seen[key]>1:raise ValueError('Sessão duplicada; coordenação deve arquivar/resolver versões.')
   validate_annotation(obj,root);found[key]=obj
  except (ValueError,TypeError,KeyError,FileNotFoundError) as error:
   public=key if key in expected else ('INDETERMINADO','','')
   issues.append({'ID':public[0],'avaliador':public[1],'sessao':public[2],'motivo':str(error) if not isinstance(error,FileNotFoundError) else 'Aprovação/entrada necessária ausente.','tipo':'sessao_invalida'})
 for (i,r,s),obj in sorted(found.items()):
  if s=='T2':
   if (i,r,'T1') not in found:issues.append({'ID':i,'avaliador':r,'sessao':s,'motivo':'T1 válida ainda ausente.','tipo':'intervalo'})
   else:
    days=(real_date(obj['acquisition_date'])-real_date(found[(i,r,'T1')]['acquisition_date'])).days
    if days<plan.get('minimum_repeat_days',14):issues.append({'ID':i,'avaliador':r,'sessao':s,'motivo':'Remarcação antes do intervalo mínimo.','dias':days,'tipo':'intervalo'})
 return found,sorted(expected-set(found)),issues
def readiness(root=ROOT):
 root=Path(root);plan=load(root/'plano.json');expected=expected_sessions(plan);blockers=[]
 try:verify_frozen(root)
 except (ValueError,FileNotFoundError) as e:blockers.append({'etapa':'integridade','motivo':str(e)})
 try:protocol(root)
 except (ValueError,KeyError,FileNotFoundError) as e:blockers.append({'etapa':'aprovacao_protocolo','motivo':'Aprovação humana ausente.' if isinstance(e,FileNotFoundError) else str(e)})
 try:validate_template(root)
 except (ValueError,KeyError,FileNotFoundError) as e:blockers.append({'etapa':'template_humano','motivo':'Template humano validado ausente ou protocolo ainda não aprovado.' if isinstance(e,FileNotFoundError) else str(e)})
 try:
  ts=load(root/'transformacoes_congeladas.json')['IDs']
  for i in plan['study_IDs']+plan.get('pilot_development_IDs',[])+[plan['template_ID']]:
   for m in ['nenhuma','controle','anatomica','multi5_rmse']:rigid_matrix(ts[i]['methods'][m])
 except (ValueError,KeyError,FileNotFoundError) as e:blockers.append({'etapa':'transformacoes','motivo':str(e)})
 found,missing,issues=scan_sessions(root)
 return {'status':'PRONTA_PARA_ANALISE' if not (blockers or missing or issues) else 'PENDENCIAS_HUMANAS_OU_TECNICAS','sessions_expected':len(expected),'sessions_found':len(found),'missing':[list(k) for k in missing],'invalid_sessions_or_intervals':issues,'blockers':blockers,'ready':not (blockers or missing or issues),'analysis_executed':False,'unidade':'conteudo; identidade clinica nao confirmada'},found
def export_check(root=ROOT):
 root=Path(root);report,found=readiness(root);out=root/'resultados';out.mkdir(exist_ok=True)
 (out/'checagem_coleta.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 pending=[]
 for i,r,s in report['missing']:pending.append({'ID':i,'avaliador':r,'sessao':s,'tipo':'sessao_ausente','motivo':'Marcação humana revisada ainda não exportada ou inválida.'})
 for item in report['invalid_sessions_or_intervals']:pending.append({k:item.get(k,'') for k in ['ID','avaliador','sessao','tipo','motivo']})
 save_csv(out/'pendencias_sessoes.csv',pending,fieldnames=['ID','avaliador','sessao','tipo','motivo'])
 tasks=load(root/'listas/A1.json')+load(root/'listas/A2.json');tracking=[]
 for t in tasks:
  key=(t['ID'],t['avaliador'],t['sessao']);obj=found.get(key);first=found.get((key[0],key[1],'T1'));minimum=''
  if t['sessao']=='T2' and first:minimum=(real_date(first['acquisition_date'])+datetime.timedelta(days=load(root/'plano.json').get('minimum_repeat_days',14))).isoformat()
  invalid=any((q['ID'],q['avaliador'],q['sessao'])==key for q in report['invalid_sessions_or_intervals'])
  tracking.append(dict(t,data_real=obj['acquisition_date'] if obj else '',data_minima_T2=minimum,estado='invalida' if invalid else 'revisada_exportada' if obj else 'pendente',revisao='confirmada_no_JSON' if obj and not invalid else 'pendente',sha256_json=sha(root/'marcacoes'/t['arquivo_json']) if obj and (root/'marcacoes'/t['arquivo_json']).exists() else ''))
 save_csv(root/'acompanhamento_atualizado.csv',tracking)
 for rater in ['A1','A2']:
  dates={i:{'ID':i,'avaliador':r,'acquisition_date':obj['acquisition_date'],'units':'metadata_only_no_coordinates'} for (i,r,s),obj in found.items() if r==rater and s=='T1' and not any((q['ID'],q['avaliador'],q['sessao'])==(i,r,s) for q in report['invalid_sessions_or_intervals'])}
  (root/'listas'/f'datas_T1_{rater}.json').write_text(json.dumps(dates,indent=2)+'\n')
 return report
