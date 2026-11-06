"""Verificação autossuficiente com a biblioteca padrão; somente leitura."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def verify(root=ROOT):
 manifest=json.loads((root/"reproducao/manifesto_pacote.json").read_text());bad=[]
 for r in manifest["arquivos"]:
  p=root/r["arquivo"]
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r["sha256"]:bad.append(r["arquivo"])
 return bad,len(manifest["arquivos"])
if __name__=="__main__":
 bad,n=verify();print(json.dumps({"arquivos":n,"integridade":not bad,"divergentes":bad},ensure_ascii=False));raise SystemExit(bool(bad))
