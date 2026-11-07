"""Translação calculada só da geometria; nunca corrige rotação ou escala."""
import numpy as np

def surface_centroid(triangles):
 t=np.asarray(triangles,dtype=np.float64)
 if t.ndim!=3 or t.shape[1:]!=(3,3) or not np.isfinite(t).all():raise ValueError("Triângulos inválidos")
 w=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)
 if w.sum()<=1e-12:raise ValueError("Superfície degenerada")
 return (t.mean(axis=1)*w[:,None]).sum(axis=0)/w.sum()

def center_pair(mesh):
 centers=[surface_centroid(mesh["arches"][a]["triangles"]) for a in ["superior","inferior"]]
 c=(centers[0]+centers[1])/2
 result={"_prepared":True,"arches":{a:{"triangles":np.ascontiguousarray(v["triangles"]-c),"normals":v["normals"].copy()} for a,v in mesh["arches"].items()}}
 return result,np.eye(3),-c
