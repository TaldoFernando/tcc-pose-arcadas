"""Regras geométricas com hipótese anatômica; não certificam anatomia."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from rigid_icp import center_pca,cloud,o3d,geodesic_deg

def unit(v):
    norm=np.linalg.norm(v)
    if norm<1e-8:raise ValueError('Referência degenerada')
    return v/norm

def anatomical_frame(upper,lower,weight=.5,vertical_mode="centroid"):
    # Para cima: vetor entre centroides do par, sem usar eixos globais.
    cu=upper.mean(0);cl=lower.mean(0);up_hint=unit(cu-cl)
    up=up_hint
    if vertical_mode=='pca_sign':
        _,axes,_=center_pca(np.concatenate([upper[::2],lower[::2]]));up=axes[:,-1]
        if np.dot(up,up_hint)<0:up=-up
    elif vertical_mode!='centroid':raise ValueError('Modo vertical inválido')
    q=lower-cl;projected=q-np.outer(q@up,up)
    _,axes=np.linalg.eigh(projected.T@projected/len(q));lateral=unit(axes[:,-1]-up*np.dot(axes[:,-1],up))
    posterior=unit(np.cross(up,lateral));x=q@lateral;y=q@posterior
    # Abertura do U: extremos posteriores presumidos mais afastados da linha média.
    hi=y>=np.quantile(y,.8);lo=y<=np.quantile(y,.2)
    width=np.quantile(x,.98)-np.quantile(x,.02);depth=np.quantile(y,.98)-np.quantile(y,.02)
    gap=(np.mean(np.abs(x[hi]))-np.mean(np.abs(x[lo])))/max(width,1e-8)
    # Centro de bbox robusta no frame LOCAL; bbox global quebraria equivariância.
    offset=((np.quantile(y,.02)+np.quantile(y,.98))/2-np.mean(y))/max(depth,1e-8)
    score=weight*gap+(1-weight)*offset
    if score<0:posterior=-posterior
    lateral=unit(np.cross(posterior,up));posterior=unit(np.cross(up,lateral))
    F=np.column_stack([lateral,posterior,up])
    assert np.linalg.det(F)>0
    return F,{'up':up.tolist(),'posterior':posterior.tolist(),'gap_score':float(gap),'centroid_bbox_score':float(offset),'sign_confidence':float(abs(score)),'weight':weight,'vertical_mode':vertical_mode,'up_centroid_hint':up_hint.tolist()}

def run_icp(points,target,init,max_iterations=60):
    reg=o3d.pipelines.registration.registration_icp(cloud(points),cloud(target),8.,init,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        o3d.pipelines.registration.ICPConvergenceCriteria(relative_fitness=1e-8,relative_rmse=1e-8,max_iteration=max_iterations))
    T=np.asarray(reg.transformation);aligned=points@T[:3,:3].T+T[:3,3]
    a=cKDTree(target).query(aligned)[0];b=cKDTree(aligned).query(target)[0]
    return {'R':T[:3,:3].tolist(),'t':T[:3,3].tolist(),'RMSE':float(np.sqrt((np.mean(a*a)+np.mean(b*b))/2)),'icp_rmse':float(reg.inlier_rmse),'fitness':float(reg.fitness)}

def normalize_anatomical(upper,lower,tu,tl,weight=.5,vertical_mode='centroid'):
    origin=(tu.mean(0)+tl.mean(0))/2;tu=tu-origin;tl=tl-origin
    Fs,source_info=anatomical_frame(upper,lower,weight,vertical_mode);Ft,target_info=anatomical_frame(tu,tl,weight,vertical_mode)
    source=np.concatenate([upper[::2],lower[::2]]);target=np.concatenate([tu[::2],tl[::2]])
    cs=source.mean(0);ct=target.mean(0)
    # Quatro inícios próximos do frame já orientado; não voltam a testar inversões.
    jitters=[np.eye(3),Rotation.from_rotvec([0,0,np.deg2rad(10)]).as_matrix(),Rotation.from_rotvec([0,0,np.deg2rad(-10)]).as_matrix(),Rotation.from_rotvec([np.deg2rad(10),0,0]).as_matrix()]
    candidates=[]
    for idx,J in enumerate(jitters):
        R=Ft@J@Fs.T;init=np.eye(4);init[:3,:3]=R;init[:3,3]=ct-R@cs
        r=run_icp(source,target,init);r['candidate']=idx;r['initial_R']=R.tolist();candidates.append(r)
    best=min(candidates,key=lambda r:r['RMSE']).copy()
    agreement=max(geodesic_deg(np.array(a['R'])@np.array(b['R']).T) for a in candidates for b in candidates)
    best.update({'candidates':candidates,'agreement_max_deg':agreement,'source_frame':source_info,'target_frame':target_info,'frame':Fs.tolist()})
    return best
