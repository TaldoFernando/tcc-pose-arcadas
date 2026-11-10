"""Executar POR PESSOA após validação no piloto; não altera normalizadores."""
import argparse,json
from pathlib import Path
from e8_common import ROOT,load,sha,verify_frozen,real_date
def freeze_definitions(date,confirmed=False,root=ROOT,definitions_file='landmarks_propostos.json'):
 root=Path(root)
 if not confirmed:raise ValueError('É necessária a confirmação humana explícita da validação.')
 real_date(date,'aprovação humana');verify_frozen(root);target=root/'protocolo_validado.json'
 if target.exists():raise ValueError('Protocolo já congelado; criar novo estudo/versionamento, sem sobrescrever.')
 if list((root/'marcacoes').glob('*.json')):raise ValueError('Não congelar novas definições após iniciar as marcações principais.')
 if not isinstance(definitions_file,str) or Path(definitions_file).name!=definitions_file or not definitions_file.endswith('.json'):raise ValueError('Arquivo de definições deve estar na pasta da Etapa 8.')
 definitions_path=root/definitions_file
 d=load(definitions_path);enabled=[x for x in d['landmarks'] if x.get('enabled',True)]
 if not enabled or d.get('approved') is not True or any(x.get('validado') is not True for x in enabled):raise ValueError('Marcar approved=true e validado=true em cada definição habilitada, após revisão humana.')
 for x in enabled:
  if x.get('arcada') not in ['superior','inferior'] or not x.get('definicao_provisoria') or not x.get('ausencia'):raise ValueError('Definir operacionalmente arcada, ponto e critérios de ausência antes de congelar.')
 if d.get('approved_date') is not None and d['approved_date']!=date:raise ValueError('Data do perfil diverge da aprovação informada.')
 code_files=['e8_common.py','slicer_markups.py','analisar.py','coleta.py']
 for extra in ['etapa8_painel_visual.py','referencias_pendentes.py','congelar_definicoes.py']:
  if (root/extra).exists():code_files.append(extra)
 result={'schema':'etapa8.protocolo_validado.v2','definitions_file':definitions_file,'definitions_sha256':sha(definitions_path),'pilot_definitions_sha256':sha(root/'landmarks_propostos.json'),'plan_sha256':sha(root/'plano.json'),'approved_by_role':'orientadora','approval_source':d.get('approval_source','confirmação humana explícita'),'approved_date':date,'code_sha256':{n:sha(root/n) for n in code_files},'enabled_landmarks':len(enabled),'definitions_developed_on_pilots_only':True,'test_normalization_rules_unchanged':True}
 with target.open('x') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--confirmar-validacao-humana',action='store_true');p.add_argument('--data',required=True);p.add_argument('--arquivo-definicoes',default='landmarks_propostos.json');a=p.parse_args()
 try:freeze_definitions(a.data,a.confirmar_validacao_humana,definitions_file=a.arquivo_definicoes)
 except ValueError as e:raise SystemExit(str(e))
 print('Definições validadas congeladas; normalização anterior intacta.')
if __name__=='__main__':main()
