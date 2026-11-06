"""Refinamentos rígidos, sem escala/reflexão. Hipóteses geométricas, não verdade anatômica."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from anatomical_pair import anatomical_frame
from rigid_icp import cloud,o3d,geodesic_deg

JITTERS=[np.eye(3),Rotation.from_rotvec([0,0,np.deg2rad(10)]).as_matrix(),Rotation.from_rotvec([0,0,np.deg2rad(-10)]).as_matrix(),Rotation.from_rotvec([np.deg2rad(10),0,0]).as_matrix()]

def combined(u,l):return np.concatenate([u[::2],l[::2]])

def posterior(u,l,F,fraction):
    direction=F[:,1]
    return np.concatenate([p[(p-p.mean(0))@direction>=np.quantile((p-p.mean(0))@direction,1-fraction)][::2] for p in [u,l]])

class Target:
    def __init__(self,upper,lower):
        self.upper=upper;self.lower=lower;self.F,_=anatomical_frame(upper,lower,1.,'pca_sign');self.points=combined(upper,lower);self.center=self.points.mean(0);self.views={}
        for name,points in [('full',self.points),('posterior_40',posterior(upper,lower,self.F,.4)),('posterior_60',posterior(upper,lower,self.F,.6))]:
            pc=cloud(points)
            if name=='full':pc.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=30))
            self.views[name]={'points':points,'cloud':pc,'tree':cKDTree(points)}

def rigid_fit(a,b):
    ca=a.mean(0);cb=b.mean(0);U,_,Vt=np.linalg.svd((a-ca).T@(b-cb));R=Vt.T@U.T
    if np.linalg.det(R)<0:Vt[-1]*=-1;R=Vt.T@U.T
    return R,cb-R@ca

def trim_icp(source,target,init,trim):
    R=init[:3,:3].copy();t=init[:3,3].copy();tree=target['tree'];points=target['points'];previous=np.inf;iterations=0
    for k in range(60):
        moved=source@R.T+t;distance,idx=tree.query(moved);valid=np.where(distance<=8)[0]
        if len(valid)<6:break
        n=max(6,int(np.ceil((1-trim)*len(valid))));keep=valid[np.argsort(distance[valid],kind='stable')[:n]]
        dR,dt=rigid_fit(moved[keep],points[idx[keep]]);R=dR@R;t=dR@t+dt;iterations=k+1
        rmse=float(np.sqrt(np.mean(distance[keep]**2)))
        if abs(previous-rmse)<1e-8 and geodesic_deg(dR)<1e-5 and np.linalg.norm(dt)<1e-6:break
        previous=rmse
    return R,t,iterations

def solve(source,view,init,mode):
    if mode.startswith('trim_'):R,t,iters=trim_icp(source,view,init,float(mode.split('_')[1])/100)
    else:
        estimator=o3d.pipelines.registration.TransformationEstimationPointToPlane() if mode=='point_plane' else o3d.pipelines.registration.TransformationEstimationPointToPoint(False)
        reg=o3d.pipelines.registration.registration_icp(cloud(source),view['cloud'],8.,init,estimator,o3d.pipelines.registration.ICPConvergenceCriteria(relative_fitness=1e-8,relative_rmse=1e-8,max_iteration=60))
        T=np.asarray(reg.transformation);R=T[:3,:3];t=T[:3,3];iters=60
    if not np.isfinite(R).all() or not np.isfinite(t).all():return {'R':init[:3,:3].tolist(),'t':init[:3,3].tolist(),'RMSE':1e12,'invalid':True}
    moved=source@R.T+t;d1=view['tree'].query(moved)[0];d2=cKDTree(moved).query(view['points'])[0]
    return {'R':R.tolist(),'t':t.tolist(),'RMSE':float(np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2)),'iterations_or_cap':iters,'invalid':False}

def refine(upper,lower,target,mode='point_point'):
    Fs,_=anatomical_frame(upper,lower,1.,'pca_sign');full=combined(upper,lower);cs=full.mean(0)
    view=target.views[mode] if mode.startswith('posterior_') else target.views['full']
    source=posterior(upper,lower,Fs,float(mode.split('_')[1])/100) if mode.startswith('posterior_') else full
    candidates=[]
    for k,J in enumerate(JITTERS):
        R=target.F@J@Fs.T;init=np.eye(4);init[:3,:3]=R;init[:3,3]=target.center-R@cs
        c=solve(source,view,init,mode);c['candidate']=k;candidates.append(c)
    best=min(candidates,key=lambda c:c['RMSE']).copy();best['candidates']=candidates;best['points_source']=len(source);best['points_target']=len(view['points'])
    return best

def aggregate_multi(results,n,selection):
    subset=results[:n]
    if selection=='rmse':idx=min(range(n),key=lambda i:subset[i]['RMSE'])
    else:
        distances=np.array([[geodesic_deg(np.array(a['R'])@np.array(b['R']).T) for b in subset] for a in subset]);idx=int(np.argmin(distances.sum(1)))
    out=subset[idx].copy();out['selected_template_index']=idx;out['n_templates']=n;out['selection']=selection;out['template_Rs']=[r['R'] for r in subset];out['template_RMSEs']=[r['RMSE'] for r in subset]
    return out
