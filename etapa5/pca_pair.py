"""Normaliza o par com uma única transformação rígida; não articula arcadas soltas."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,argparse
import numpy as np
from rigid_icp import read_triangles,sample_surface,normalize_points

def reference(upper,lower,method):
    if method=='superior': return upper
    if method=='combinada': return np.concatenate([upper[::2],lower[::2]])
    raise ValueError('Método deve ser superior ou combinada')

def apply_transform(points,R,t): return np.asarray(points)@np.asarray(R).T+np.asarray(t)

def normalize_pair_points(upper,lower,template_upper,template_lower,method='superior'):
    # Um só centro de referência para os dois métodos: centro combinado do template.
    origin=(template_upper.mean(axis=0)+template_lower.mean(axis=0))/2
    target=reference(template_upper-origin,template_lower-origin,method)
    result=normalize_points(reference(upper,lower,method),target)
    result['reference_method']=method;result['template_origin_native']=origin.tolist()
    result['convention']='Mesmos R e t: x_saida = R @ x_entrada + t, superior E inferior; sem escala/reflexão'
    return result

def normalize_pair(upper,lower,template_upper,template_lower,method='superior',seed=20261105):
    paths=[upper,lower,template_upper,template_lower]
    seeds=[seed+11,seed+12,seed+1,seed+2]
    clouds=[sample_surface(read_triangles(p),2048,s) for p,s in zip(paths,seeds)]
    return normalize_pair_points(*clouds,method)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('upper');p.add_argument('lower');p.add_argument('template_upper');p.add_argument('template_lower');p.add_argument('--method',choices=['superior','combinada'],default='superior');p.add_argument('--output',required=True)
    a=p.parse_args();Path(a.output).write_text(json.dumps(normalize_pair(a.upper,a.lower,a.template_upper,a.template_lower,a.method),indent=2,ensure_ascii=False))
