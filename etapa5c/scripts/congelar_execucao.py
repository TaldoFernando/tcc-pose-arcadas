"""Reconstrução do passo de manifesto para reprodução em uma cópia limpa.
Adicionado após a execução original; não altera nem substitui os congelamentos existentes.
"""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[2];O=ROOT/"etapa5c"
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
def main():
 targets=[O/"desenvolvimento.json",O/"teste_bloqueado/entradas.json",O/"congelamento_execucao.json"]
 assert not any(p.exists() for p in targets),"Somente em cópia de reprodução limpa; não sobrescrever congelamentos."
 assert not (O/"resultados/predicoes_OOF.csv").exists() and not (O/"teste_bloqueado/abertura.json").exists()
 for name,h in load(O/"congelamento.json")["files"].items():assert sha(ROOT/name)==h,name
 split=load(O/"divisao.json");contents=load(O/"conteudos_elegiveis.json")
 dev=[c for c in contents if c["ID"] in split["dev_IDs"]];test=[c for c in contents if c["ID"] in split["test_IDs"]]
 (O/"teste_bloqueado").mkdir(exist_ok=True);(O/"resultados").mkdir(exist_ok=True);(O/"checkpoints").mkdir(exist_ok=True);(O/"qa").mkdir(exist_ok=True)
 save(targets[0],dev);save(targets[1],test)
 files=[O/"scripts"/n for n in ["classificador.py","avaliar.py","teste_final.py"]]+targets[:2]
 for c in dev:
  files.extend([ROOT/"etapa7b/features"/(c["ID"]+".npz"),ROOT/"etapa7b/correcoes_v2/features"/(c["ID"]+".npz")])
 save(targets[2],{"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"before_training_and_OOF":True,"test_performance_not_computed":True,"files":{str(p.relative_to(ROOT)):sha(p) for p in files},"reconstrucao_para_reproducao":True})
 print("Manifesta de execução criado antes de treinar; teste permanece bloqueado.")
if __name__=="__main__":main()
