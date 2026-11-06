"""Normalização rígida local, sem escala/reflexão. Convenção: x_saida = R @ x_entrada + t."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import itertools,json,argparse
from pathlib import Path
import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree

SIGNS=[np.diag(s) for s in itertools.product([-1,1],repeat=3) if np.prod(s)==1]

def read_triangles(path):
    """Lê STL binário sem modificar o arquivo."""
    raw=Path(path).read_bytes(); n=int.from_bytes(raw[80:84],'little')
    if len(raw)!=84+n*50: raise ValueError('Esperado STL binário válido')
    dtype=np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('atributo','<u2')])
    tri=np.frombuffer(raw,dtype,offset=84,count=n)['vertices'].astype(np.float64)
    if not np.isfinite(tri).all(): raise ValueError('Coordenadas inválidas')
    return tri

def sample_surface(tri,count=2048,seed=20261029):
    """Amostra área uniformemente, com semente fixa e ordem original das faces."""
    areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    rng=np.random.default_rng(seed); ids=rng.choice(len(tri),count,p=areas/areas.sum())
    u=rng.random(count)**.5; v=rng.random(count)
    return (1-u[:,None])*tri[ids,0]+(u*(1-v))[:,None]*tri[ids,1]+(u*v)[:,None]*tri[ids,2]

def center_pca(points):
    """Centroide da amostra da superfície e PCA recalculados a cada chamada."""
    center=points.mean(axis=0); q=points-center
    vals,axes=np.linalg.eigh(q.T@q/len(q)); vals=vals[::-1];axes=axes[:,::-1]
    if np.linalg.det(axes)<0: axes[:,-1]*=-1
    return center,axes,vals

def cloud(points):
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.asarray(points,dtype=float)))

def geodesic_deg(rotation):
    return float(np.degrees(np.arccos(np.clip((np.trace(rotation)-1)/2,-1,1))))

def normalize_points(points,template_points,max_iterations=60,threshold=8.):
    """Testa quatro inicializações PCA próprias e refina cada uma por ICP Open3D.

    Seleção pelo RMSE simétrico SEM corte de correspondências, para não favorecer
    soluções com poucos inliers. O RMSE ICP (com corte) é devolvido separadamente.
    """
    cs,As,vs=center_pca(points); ct,At,vt=center_pca(template_points)
    source=cloud(points);target=cloud(template_points);tree=cKDTree(template_points)
    candidates=[]
    for idx,S in enumerate(SIGNS):
        R=At@S@As.T; init=np.eye(4);init[:3,:3]=R;init[:3,3]=ct-R@cs
        reg=o3d.pipelines.registration.registration_icp(source,target,threshold,init,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
            o3d.pipelines.registration.ICPConvergenceCriteria(relative_fitness=1e-8,relative_rmse=1e-8,max_iteration=max_iterations))
        T=np.asarray(reg.transformation); aligned=points@T[:3,:3].T+T[:3,3]
        d1=tree.query(aligned)[0]; d2=cKDTree(aligned).query(template_points)[0]
        rmse=float(np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2))
        candidates.append({'R':T[:3,:3].tolist(),'t':T[:3,3].tolist(),'RMSE':rmse,
          'icp_inlier_rmse':float(reg.inlier_rmse),'fitness':float(reg.fitness),'candidate':idx})
    best=min(candidates,key=lambda r:r['RMSE']).copy()
    best['candidates']=candidates;best['pca_eigenvalues']=vs.tolist();best['samples']=len(points)
    best['convention']='x_saida = R @ x_entrada + t; sem escala; RMSE simétrico sem corte'
    return best

def normalize_stl(source,template,count=2048):
    return normalize_points(sample_surface(read_triangles(source),count),sample_surface(read_triangles(template),count))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('template');parser.add_argument('--output',required=True);parser.add_argument('--samples',type=int,default=2048)
    args=parser.parse_args(); result=normalize_stl(args.source,args.template,args.samples)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False))
