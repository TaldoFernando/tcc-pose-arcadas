from common import *
import shutil
manifest=[]
for p in load_json('pares.json'):
 for a in ['superior','inferior']:
  source=ROOT/'etapa2'/p[a]['arquivo'];dest=OUT/p[a]['arquivo'];dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():shutil.copy2(source,dest)
  assert digest(dest)==p[a]['sha256']
  manifest.append({'id':p['id'],'arcada':a,'copia':str(dest.relative_to(OUT)),'fonte':str(source),'sha256':p[a]['sha256']})
 for a in ['superior','inferior']:
  for level in ['leve','forte','preview']:
   source=ROOT/'etapa2/cache'/p['id']/f'{a}_{level}.npz';dest=OUT/'cache'/p['id']/source.name;dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():shutil.copy2(source,dest)
save_json('manifesto_copias.json',manifest)
print('138 STL e geometrias experimentais copiados sem alterações.')
