from common import *
from scipy.spatial.transform import Rotation

def perturb(pair,trial_index):
    idx=int(pair['id'][1:])-1;k=trial_index
    seed=SEED+1000*(idx+1)+k;rng=np.random.default_rng(seed);Q=Rotation.random(random_state=rng).as_matrix();shift=rng.uniform(-100,100,3)
    clouds=[];metadata=[]
    for a in ['superior','inferior']:
        level=str(rng.choice(['leve','forte']));tri=np.load(OUT/'cache'/pair['id']/f'{a}_{level}.npz')['tri'];point_seed=int(rng.integers(1,2**31))
        pts=sample_surface(tri,2048,point_seed);pts=pts@Q.T+shift;pts+=rng.normal(0,.15,pts.shape)
        fraction=float(rng.uniform(.10,.30));anchor=int(rng.integers(len(pts)));d=np.linalg.norm(pts-pts[anchor],axis=1);count=int(round(len(pts)*fraction));order=np.argsort(d,kind='stable');keep=np.ones(len(pts),bool);keep[order[:count]]=False
        clouds.append(pts[keep]);metadata.append({'seed':point_seed,'level':level,'removed_fraction':count/len(pts)})
    return clouds,Q,shift,seed,metadata

def baseline_points(pair):
    return (sample_surface(read_triangles(OUT/pair['superior']['arquivo']),2048,SEED+11),sample_surface(read_triangles(OUT/pair['inferior']['arquivo']),2048,SEED+12))
