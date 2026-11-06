"""Executar POR PESSOA após validação no piloto; não altera normalizadores."""
from pathlib import Path
import argparse,datetime,json
from e8_common import ROOT,load,sha,verify_frozen
def main():
 p=argparse.ArgumentParser();p.add_argument('--confirmar-validacao-humana',action='store_true');p.add_argument('--data',required=True);a=p.parse_args()
 if not a.confirmar_validacao_humana:raise SystemExit('É necessária a confirmação humana explícita da validação.')
 datetime.date.fromisoformat(a.data);verify_frozen();target=ROOT/'protocolo_validado.json'
 if target.exists():raise SystemExit('Protocolo já congelado; criar novo estudo/versionamento, sem sobrescrever.')
 if list((ROOT/'marcacoes').glob('*.json')):raise SystemExit('Não congelar novas definições após iniciar as marcações principais.')
 d=load(ROOT/'landmarks_propostos.json')
 if not d.get('approved') or any(not x.get('validado') for x in d['landmarks'] if x.get('enabled',True)):raise SystemExit('Marcar approved=true e validado=true em cada definição habilitada, após revisão humana. Pontos não aplicáveis ao estudo podem ser desabilitados com enabled=false.')
 result={'definitions_sha256':sha(ROOT/'landmarks_propostos.json'),'plan_sha256':sha(ROOT/'plano.json'),'approved_by_role':'orientadora','approved_date':a.data,'code_sha256':{n:sha(ROOT/n) for n in ['e8_common.py','slicer_markups.py','analisar.py']},'definitions_pilot_only':True,'test_normalization_rules_unchanged':True};target.write_text(json.dumps(result,indent=2));print('Definições validadas congeladas; normalização anterior intacta.')
if __name__=='__main__':main()
