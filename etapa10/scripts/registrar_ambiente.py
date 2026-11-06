from pathlib import Path
import importlib.metadata as md
import json,platform,sys
OUT=Path(__file__).resolve().parents[1]/"reproducao"
kind=sys.argv[1]
packages={}
for d in md.distributions():
 name=d.metadata.get("Name")
 if name:packages[name]=d.version
result={"python":platform.python_version(),"implementacao":platform.python_implementation(),"sistema":platform.system(),"arquitetura":platform.machine(),"pacotes":dict(sorted(packages.items(),key=lambda x:x[0].lower()))}
(OUT/f"versoes_{kind}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
(OUT/f"requirements_{kind}.txt").write_text("\n".join(f"{k}=={v}" for k,v in result["pacotes"].items())+"\n")
print(kind,len(packages),"pacotes")
