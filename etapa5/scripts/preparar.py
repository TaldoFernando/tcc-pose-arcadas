from common import *
import re,shutil,collections
from scipy.spatial.transform import Rotation
pairs=json.loads((ROOT/'etapa4/pares.json').read_text());private=[];clean=[];labels=[];issues=[];manifest=[]
for p in pairs:
 identifier=p['id'];folder=p['paciente'];parts=folder.split('/',1);parent=re.findall(r'grupo\s*(\d+)',parts[0],re.I);text=parts[-1];group=int(parent[0]) if parent else None
 gs=sorted(set(int(x) for x in re.findall(r'goslon\s*\(?\s*([1-5])',text,re.I)));gg=sorted(set(int(x) for x in re.findall(r'grupo\s*(\d+)',text,re.I)));goslon=gs[0] if len(gs)==1 else None
 labels.append({'ID':identifier,'grupo':group,'goslon':goslon,'fonte':'nome da pasta'})
 reasons=[]
 if len(gs)!=1:reasons.append('GOSLON ausente ou múltiplo')
 if gg and gg!=[group]:reasons.append('grupo textual difere do diretório de grupo')
 expected={1:[1,2],2:[3],3:[4,5]}
 if goslon is not None and goslon not in expected.get(group,[]):reasons.append('grupo incompatível com mapeamento de auditoria 1→1/2;2→3;3→4/5')
 if reasons:issues.append({'ID':identifier,'grupo':group,'grupo_textual':json.dumps(gg),'goslon':goslon,'motivo':'; '.join(reasons)})
 private.append({'ID':identifier,'pasta':folder,'superior_fonte':p['superior']['fonte_inventario'],'inferior_fonte':p['inferior']['fonte_inventario']})
 c={'id':identifier,'superior_axes':p['superior_axes']}
 for a in ['superior','inferior']:
  source=ROOT/'etapa4'/p[a]['arquivo'];target=OUT/'copias'/identifier/f'{a}.stl';target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():shutil.copy2(source,target)
  assert digest(target)==p[a]['sha256'],identifier
  c[a]={'arquivo':str(target.relative_to(OUT)),'sha256':p[a]['sha256']}
  manifest.append({'ID':identifier,'arcada':a,'arquivo':c[a]['arquivo'],'sha256':p[a]['sha256']})
 for a in ['superior','inferior']:
  for level in ['leve','forte']:
   source=ROOT/'etapa4/cache'/identifier/f'{a}_{level}.npz';target=OUT/'cache'/identifier/source.name;target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists():shutil.copy2(source,target)
 clean.append(c)
csv_save('privado/id_pasta_local.csv',private);csv_save('rotulos_local.csv',labels);save('pares_ids.json',clean);save('manifesto_ids.json',manifest)
# Aliases de conteúdo com rótulos conflitantes são listados sem nomes.
groups=collections.defaultdict(list);bylabel={r['ID']:r for r in labels}
for p in clean:groups[key(p)].append(p['id'])
for ids in groups.values():
 values={bylabel[i]['goslon'] for i in ids};gv={bylabel[i]['grupo'] for i in ids}
 if len(values)>1 or len(gv)>1:
  for i in ids:issues.append({'ID':i,'grupo':bylabel[i]['grupo'],'grupo_textual':'','goslon':bylabel[i]['goslon'],'motivo':'mesmo conteúdo com rótulos diferentes; aliases '+','.join(ids)})
csv_save('inconsistencias_rotulos.csv',issues or [{'ID':'','grupo':'','grupo_textual':'','goslon':'','motivo':'nenhuma inconsistência encontrada'}])
# Clouds reconstituídos sem rótulos, mesmas perturbações das etapas anteriores.
for p in clean:
 identifier=p['id'];path=OUT/'clouds'/f'{identifier}.npz';path.parent.mkdir(exist_ok=True)
 if path.exists():continue
 data={}
 for j,a in enumerate(['superior','inferior']):data[a+'_base']=sample_surface(read_triangles(OUT/p[a]['arquivo']),2048,SEED+11+j)
 for k in range(20):
  seed=SEED+1000*int(identifier[1:])+k;rng=np.random.default_rng(seed);Q=Rotation.random(random_state=rng).as_matrix();t=rng.uniform(-100,100,3);data[f'Q{k:02d}']=Q;data[f't{k:02d}']=t
  for a in ['superior','inferior']:
   level=str(rng.choice(['leve','forte']));tri=np.load(OUT/'cache'/identifier/f'{a}_{level}.npz')['tri'];ps=int(rng.integers(1,2**31));points=sample_surface(tri,2048,ps);points=points@Q.T+t;points+=rng.normal(0,.15,points.shape)
   fraction=float(rng.uniform(.10,.30));anchor=int(rng.integers(len(points)));d=np.linalg.norm(points-points[anchor],axis=1);n=int(round(len(points)*fraction));order=np.argsort(d,kind='stable');keep=np.ones(len(points),bool);keep[order[:n]]=False;data[f'{a}{k:02d}']=points[keep]
 np.savez_compressed(path,**data)
print('PREPARADO: IDs',len(clean),'linhas de inconsistências',len(issues),'nenhum nome nos relatórios.')
