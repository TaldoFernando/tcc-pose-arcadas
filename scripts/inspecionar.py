"""Auditoria local dos STL; nenhuma informação é enviada à rede."""
from pathlib import Path
import zipfile, json, csv, hashlib, itertools, collections, subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
ZIP=Path.home()/'Downloads/escaneamentos para projeto IA-20261019T173556Z-1-001.zip'
DEST=ROOT/'dados'

def analisar(p):
    raw=p.read_bytes(); n=int.from_bytes(raw[80:84],'little')
    if len(raw)!=84+50*n: raise ValueError('STL não binário ou comprimento inválido')
    dt=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')])
    tri=np.frombuffer(raw,dt,offset=84,count=n)['v'].astype(float)
    if not np.isfinite(tri).all(): raise ValueError('Coordenadas não finitas')
    v,inv=np.unique(tri.reshape(-1,3),axis=0,return_inverse=True); faces=inv.reshape(-1,3)
    cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); areas=np.linalg.norm(cross,axis=1)/2
    total=areas.sum(); centroid=(tri.mean(axis=1)*areas[:,None]).sum(axis=0)/total
    # Momentos exatos da superfície triangular: PCA independente da densidade de tesselação.
    centered=tri-centroid; sums=centered.sum(axis=1)
    moment=(np.einsum('nti,ntj,n->ij',centered,centered,areas)+np.einsum('ni,nj,n->ij',sums,sums,areas))/(12*total)
    vals,axes=np.linalg.eigh(moment); vals=vals[::-1]; axes=axes[:,::-1]
    if np.linalg.det(axes)<0: axes[:,-1]*=-1
    edges=np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
    _,counts=np.unique(edges,axis=0,return_counts=True)
    # Maior área em um plano: candidatos por normais arredondadas; apenas indício de base.
    normals=cross/np.maximum(2*areas[:,None],1e-30)
    for j in range(3):
        mask=(np.abs(normals[:,j])>1e-8)&(np.all(np.abs(normals[:,:j])<=1e-8,axis=1))
        normals[mask & (normals[:,j]<0)]*=-1
    offsets=np.einsum('ni,ni->n',normals,tri[:,0])
    keys=np.column_stack([np.round(normals,2),np.round(offsets,1)])
    _,ids=np.unique(keys,axis=0,return_inverse=True)
    planar=float(np.bincount(ids,weights=areas).max()/total)
    rel=p.relative_to(DEST); parts=rel.parts; name=p.name.lower()
    arch='superior' if any(s in name for s in ['maxillary','upperjaw']) else 'inferior' if any(s in name for s in ['mandibular','lowerjaw']) else 'registro_mordida' if 'biteaverage' in name else 'indeterminada'
    r={'arquivo':str(rel),'grupo':parts[1],'pasta_paciente':parts[2],'arcada':arch,'sha256':hashlib.sha256(raw).hexdigest(),'triangulos':n,'vertices_unicos':len(v),'area_unidades2':float(total),'watertight':bool(np.all(counts==2)),'arestas_abertas':int((counts==1).sum()),'arestas_nao_manifold':int((counts>2).sum()),'triangulos_degenerados':int((areas==0).sum()),'base_gesso':'INDETERMINADA','base_indicio_plano':planar>=.03,'maior_fracao_area_coplanar_aprox':planar,'unidade':'mm_ASSUMIDO_STL_SEM_UNIDADE'}
    for label,arr in [('bbox_min',v.min(axis=0)),('bbox_max',v.max(axis=0)),('bbox_dim',np.ptp(v,axis=0)),('centroide_superficie',centroid),('pca_autovalores',vals)]:
        for ax,x in zip('xyz',arr): r[label+'_'+ax]=float(x)
    r['pca_eixos_colunas']=json.dumps(axes.tolist()); r['pca_razao_1_2']=float(vals[0]/vals[1]);r['pca_razao_2_3']=float(vals[1]/vals[2])
    return r,axes

def main():
    with zipfile.ZipFile(ZIP) as z:
        for entry in z.infolist():
            target=(DEST/entry.filename).resolve()
            if not target.is_relative_to(DEST.resolve()): raise ValueError('Caminho inseguro')
        z.extractall(DEST)
        manifest=[{'arquivo':i.filename,'bytes':i.file_size,'pasta':i.is_dir()} for i in z.infolist()]
    (ROOT/'relatorios/estrutura.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    for archive in DEST.rglob('*.rar'):
        target=archive.parent/'extraido_rar'; target.mkdir(exist_ok=True)
        subprocess.run(['tar','-xf',str(archive),'-C',str(target)],check=True)
    cache={}
    if (ROOT/'inventario.csv').exists():
        with (ROOT/'inventario.csv').open() as f:
            for r in csv.DictReader(f):
                for k in ['triangulos','vertices_unicos','arestas_abertas','arestas_nao_manifold','triangulos_degenerados']: r[k]=int(r[k])
                for k in ['watertight','base_indicio_plano']: r[k]=r[k]=='True'
                cache[r['arquivo']]=r
    rows=[]; matrices=[]
    paths=sorted(DEST.rglob('*.stl'))
    for i,p in enumerate(paths):
        key=str(p.relative_to(DEST))
        if key in cache and hashlib.sha256(p.read_bytes()).hexdigest()==cache[key]['sha256']:
            r=cache[key]; a=np.array(json.loads(r['pca_eixos_colunas']))
        else: r,a=analisar(p)
        rows.append(r); matrices.append(a)
        print(f'{i+1}/{len(paths)}',flush=True)
    with (ROOT/'inventario.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    signs=[np.diag(s) for s in itertools.product([-1,1],repeat=3) if np.prod(s)==1]
    comparisons=[]
    for arch in ['superior','inferior','indeterminada','registro_mordida']:
        seen=set(); idx=[]
        for i,r in enumerate(rows):
            if r['arcada']==arch and r['sha256'] not in seen: seen.add(r['sha256']);idx.append(i)
        for i,j in itertools.combinations(idx,2):
            if rows[i]['pasta_paciente']==rows[j]['pasta_paciente']: continue
            angle=min(np.degrees(np.arccos(np.clip((np.trace(matrices[i].T@matrices[j]@s)-1)/2,-1,1))) for s in signs)
            comparisons.append({'arcada':arch,'arquivo_a':rows[i]['arquivo'],'arquivo_b':rows[j]['arquivo'],'angulo_graus':float(angle)})
    with (ROOT/'relatorios/pca_pares.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['arcada','arquivo_a','arquivo_b','angulo_graus']);w.writeheader();w.writerows(comparisons)
    stats={}
    for arch in sorted(set(c['arcada'] for c in comparisons)):
        x=[c['angulo_graus'] for c in comparisons if c['arcada']==arch]
        stats[arch]={'pares':len(x),'min':min(x),'mediana':float(np.median(x)),'max':max(x)}
    config={'etapa':'Passo 0 — auditoria dos dados reais','fonte_zip':str(ZIP),'arquivos_zip':len(manifest),'stl':len(rows),'stl_unicos_sha256':len(set(r['sha256'] for r in rows)),'pastas_paciente_com_stl':len(set((r['grupo'],r['pasta_paciente']) for r in rows)),'arcadas':dict(collections.Counter(r['arcada'] for r in rows)),'watertight':dict(collections.Counter(str(r['watertight']) for r in rows)),'unidade':{'valor':'mm','status':'PLACEHOLDER','motivo':'STL não declara unidade; dimensões reportadas em unidades nativas, interpretadas provisoriamente como mm.'},'pca':{'metodo':'momentos exatos da superfície ponderados por área; autovalores decrescentes; 4 sinais próprios; pares da mesma arcada, SHA256 únicos, pastas distintas','dispersao_graus':stats,'limite_pose_parecida_graus':{'valor':10,'status':'PLACEHOLDER_HEURISTICO'},'limite':'PCA mede eixos geométricos, não valida orientação anatômica; simetrias e bases influenciam.'},'bases':{'status':'INDETERMINADA','metodo':'Indício automático: maior agrupamento de planos com normais arredondadas a 0.01 e offsets a 0.1 >=3% da área; não confirma material ou anatomia. Não recortar sem revisão.'},'treino':{k:'PLACEHOLDER — script ausente no repositório e no ZIP' for k in ['projecao','fov','extensao_ortografica','distancia_camera','resolucao','fundo','iluminacao','material','centralizacao','escala','orientacao_canonica','tratamento_bases']},'cameras':{v:{'posicao':'PLACEHOLDER','direcao':'PLACEHOLDER','up':'PLACEHOLDER','angulo':'PLACEHOLDER'} for v in ['Angulada','Direita','Esquerda','Up','Frontal','Inferior']}}
    (ROOT/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
    print(json.dumps(config,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
