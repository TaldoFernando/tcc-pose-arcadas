import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MPLCONFIGDIR']='/private/tmp/goslon-etapa2-mpl'
from pathlib import Path
import sys,csv,json,hashlib,itertools
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rigid_icp import *
from pca_pair import normalize_pair_points,apply_transform
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'etapa4';SEED=20261105

def save_json(path,value):
    p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2))

def save_csv(path,rows):
    p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def load_json(path):return json.loads((OUT/path).read_text())

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def angular_axes(A,B):return min(geodesic_deg(A.T@B@S) for S in SIGNS)

def mesh_from_tri(tri):
    mesh=o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(tri.reshape(-1,3)),o3d.utility.Vector3iVector(np.arange(tri.size//3).reshape(-1,3)))
    mesh.remove_duplicated_vertices();return mesh

def simplify(tri,target):
    mesh=mesh_from_tri(tri);mesh=mesh.simplify_quadric_decimation(int(target))
    return np.asarray(mesh.vertices)[np.asarray(mesh.triangles)]

def scene(tri):
    sc=o3d.t.geometry.RaycastingScene()
    sc.add_triangles(o3d.core.Tensor(tri.reshape(-1,3).astype(np.float32)),o3d.core.Tensor(np.arange(tri.size//3,dtype=np.uint32).reshape(-1,3)))
    return sc

def dist_to_mesh(points,sc):
    out=[]
    for i in range(0,len(points),100000):out.append(sc.compute_distance(o3d.core.Tensor(np.asarray(points[i:i+100000],dtype=np.float32))).numpy().astype(float))
    return np.concatenate(out)

def proximity(upper,lower):
    """Mínimo aproximado: vértices e 20k amostras para superfície triangular oposta.
    É limite superior da distância exata, não prova de contato/interseção.
    """
    su=scene(upper);sl=scene(lower)
    u=np.unique(upper.reshape(-1,3),axis=0);l=np.unique(lower.reshape(-1,3),axis=0)
    pu=sample_surface(upper,20000,SEED);pl=sample_surface(lower,20000,SEED+1)
    du=dist_to_mesh(np.concatenate([u,pu]),sl);dl=dist_to_mesh(np.concatenate([l,pl]),su)
    sampledu=du[len(u):];sampledl=dl[len(l):]
    return {'distancia_min_aproximada':float(min(du.min(),dl.min())),
      'percentil1_distancia_superior_inferior':float(np.percentile(sampledu,1)),
      'fracao_area_superior_a_1unid':float(np.mean(sampledu<=1)),
      'fracao_area_inferior_a_1unid':float(np.mean(sampledl<=1)),
      'arestas_maior_comprimento':float(max(np.linalg.norm(upper[:,1]-upper[:,0],axis=1).max(),np.linalg.norm(upper[:,2]-upper[:,0],axis=1).max(),np.linalg.norm(upper[:,2]-upper[:,1],axis=1).max())),
      'metodo_distancia':'aproximação bidirecional vértice/amostra-superfície; limite superior, não distância exata triângulo-triângulo'}

def preview_pair(upper,lower,path,title,transformation=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    if transformation:
        upper=apply_transform(upper,transformation['R'],transformation['t']);lower=apply_transform(lower,transformation['R'],transformation['t'])
    allv=np.concatenate([upper.reshape(-1,3),lower.reshape(-1,3)]);low=allv.min(0);high=allv.max(0);mid=(low+high)/2;span=max(high-low)
    fig=plt.figure(figsize=(12,4));light=np.array([.3,-.4,1]);light/=np.linalg.norm(light)
    for i,(elev,azim,label) in enumerate([(0,-90,'Frontal geométrica'),(0,0,'Lateral geométrica'),(90,-90,'Oclusal geométrica')]):
        ax=fig.add_subplot(1,3,i+1,projection='3d')
        for tri,color in [(upper,np.array([.3,.65,.92])),(lower,np.array([.95,.56,.28]))]:
            normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-20)
            shade=.30+.65*np.abs(normals@light);ax.add_collection3d(Poly3DCollection(tri,facecolor=shade[:,None]*color,edgecolor='none'))
        for j,fn in enumerate([ax.set_xlim,ax.set_ylim,ax.set_zlim]):fn(mid[j]-span*.53,mid[j]+span*.53)
        ax.set_box_aspect((1,1,1));ax.view_init(elev,azim);ax.set_title(label,fontsize=10);ax.set_xlabel('X');ax.set_ylabel('Y');ax.set_zlabel('Z')
        if i==0:ax.set_yticks([]);ax.set_ylabel('')
        if i==1:ax.set_xticks([]);ax.set_xlabel('')
        if i==2:ax.set_zticks([]);ax.set_zlabel('')
    fig.suptitle(title+' | azul: superior; laranja: inferior',fontsize=10);fig.tight_layout();fig.savefig(OUT/path,dpi=130);plt.close(fig)
