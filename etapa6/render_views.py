"""Rasterizador local CPU: seis vistas, sem janela, GPU, rede ou autoenquadramento.

Recebe triângulos em coordenadas já escolhidas pelo chamador. Não normaliza,
não recorta bases e não ajusta escala por paciente. Configuração PLACEHOLDER
é recusada, salvo opção explícita allow_uncalibrated para demonstrações.
"""
from pathlib import Path
import copy, json, re, time
import numpy as np
from numba import njit
from PIL import Image

VIEWS=('Angulada','Direita','Esquerda','Up','Frontal','Inferior')

def read_stl(path):
    data=Path(path).read_bytes()
    if len(data)>=84:
        count=int.from_bytes(data[80:84],'little')
        if 84+50*count==len(data):
            dt=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
            tri=np.frombuffer(data,dtype=dt,count=count,offset=84)['vertices'].astype(np.float64)
            if not np.isfinite(tri).all():raise ValueError('STL contém coordenadas não finitas')
            return tri
    vertices=[]
    for line in data.decode('ascii').splitlines():
        words=line.split()
        if words and words[0].lower()=='vertex':vertices.append([float(x) for x in words[1:4]])
    tri=np.asarray(vertices,float).reshape(-1,3,3)
    if not len(tri) or not np.isfinite(tri).all():raise ValueError('STL inválido')
    return tri

def _triangles(value):
    a=read_stl(value) if isinstance(value,(str,Path)) else np.asarray(value,dtype=np.float64)
    if a.ndim!=3 or a.shape[1:]!=(3,3) or not len(a) or not np.isfinite(a).all():raise ValueError('Esperado array finito Nx3x3')
    return a

def prepare_mesh(mesh,shading='smooth'):
    """Prepara uma vez; reutilizar retorno em renderizações/otimização."""
    if isinstance(mesh,dict) and mesh.get('_prepared',False):return mesh
    if not isinstance(mesh,dict):mesh={'superior':mesh}
    out={'_prepared':True,'arches':{}}
    for arch in ('superior','inferior'):
        if arch not in mesh:continue
        tri=_triangles(mesh[arch]);faces_normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        if shading=='smooth':
            vertices,inverse=np.unique(tri.reshape(-1,3),axis=0,return_inverse=True);normals=np.zeros_like(vertices)
            np.add.at(normals,inverse,np.repeat(faces_normal,3,axis=0));normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-20);normals=normals[inverse].reshape(-1,3,3)
        elif shading=='flat':
            faces_normal/=np.maximum(np.linalg.norm(faces_normal,axis=1,keepdims=True),1e-20);normals=np.repeat(faces_normal[:,None,:],3,axis=1)
        else:raise ValueError('shading deve ser smooth ou flat')
        out['arches'][arch]={'triangles':np.ascontiguousarray(tri),'normals':np.ascontiguousarray(normals)}
    if not out['arches']:raise ValueError('Nenhuma arcada fornecida')
    return out

def camera_basis(camera):
    pos=np.asarray(camera['position'],float);target=np.asarray(camera['target'],float);up=np.asarray(camera['up'],float)
    if pos.shape!=(3,) or target.shape!=(3,) or up.shape!=(3,) or not np.isfinite(np.r_[pos,target,up]).all():raise ValueError('Extrínsecos inválidos')
    f=target-pos
    if np.linalg.norm(f)<1e-9:raise ValueError('position e target coincidentes')
    f/=np.linalg.norm(f);right=np.cross(f,up)
    if np.linalg.norm(right)<1e-9:raise ValueError('up paralelo à direção')
    right/=np.linalg.norm(right);u=np.cross(right,f)
    return pos,np.column_stack([right,u,f])

@njit(cache=True)
def _raster(pixels,z,normals,width,height,perspective,near,far,bg,material,ambient,diffuse,light,two_sided):
    image=np.empty((height,width,3),np.uint8);depth=np.full((height,width),np.inf)
    for y in range(height):
        for x in range(width):
            for c in range(3):image[y,x,c]=bg[c]
    for k in range(len(pixels)):
        if min(z[k,0],z[k,1],z[k,2])<near-1e-9 or max(z[k,0],z[k,1],z[k,2])>far+1e-9:continue
        x0,y0=pixels[k,0,0],pixels[k,0,1];x1,y1=pixels[k,1,0],pixels[k,1,1];x2,y2=pixels[k,2,0],pixels[k,2,1]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-12:continue
        xmin=max(0,int(np.floor(min(x0,x1,x2))));xmax=min(width-1,int(np.ceil(max(x0,x1,x2))));ymin=max(0,int(np.floor(min(y0,y1,y2))));ymax=min(height-1,int(np.ceil(max(y0,y1,y2))))
        for y in range(ymin,ymax+1):
            for x in range(xmin,xmax+1):
                px=x+.5;py=y+.5;a=((y1-y2)*(px-x2)+(x2-x1)*(py-y2))/den;b=((y2-y0)*(px-x2)+(x0-x2)*(py-y2))/den;c=1-a-b
                if min(a,b,c)<-1e-9:continue
                if perspective:
                    inv=a/z[k,0]+b/z[k,1]+c/z[k,2];d=1/inv;aa=a/z[k,0]*d;bb=b/z[k,1]*d;cc=c/z[k,2]*d
                else:d=a*z[k,0]+b*z[k,1]+c*z[k,2];aa=a;bb=b;cc=c
                if d>=depth[y,x]:continue
                nx=aa*normals[k,0,0]+bb*normals[k,1,0]+cc*normals[k,2,0];ny=aa*normals[k,0,1]+bb*normals[k,1,1]+cc*normals[k,2,1];nz=aa*normals[k,0,2]+bb*normals[k,1,2]+cc*normals[k,2,2];nn=np.sqrt(nx*nx+ny*ny+nz*nz)
                if nn>1e-20:nx/=nn;ny/=nn;nz/=nn
                if two_sided and nz>0:nx=-nx;ny=-ny;nz=-nz
                intensity=ambient+diffuse*max(0,nx*light[0]+ny*light[1]+nz*light[2]);depth[y,x]=d
                for color in range(3):image[y,x,color]=np.uint8(min(255,max(0,np.rint(material[color]*intensity))))
    return image,depth

def _clip_depth(q,normals,near,far):
    """Clipa triângulos nos planos de profundidade antes da perspectiva."""
    z=q[:,:,2];inside=((z>=near)&(z<=far)).all(axis=1)
    if inside.all():return q,normals
    crosses=(z.max(axis=1)>=near)&(z.min(axis=1)<=far)&~inside
    qs=[q[inside]];ns=[normals[inside]]
    for tri,normal in zip(q[crosses],normals[crosses]):
        points=[p.copy() for p in tri];attributes=[n.copy() for n in normal]
        for plane,lower in [(near,True),(far,False)]:
            if not points:break
            newp=[];newn=[]
            for i,current in enumerate(points):
                previous=points[i-1];nc=attributes[i];np_=attributes[i-1];ic=current[2]>=plane if lower else current[2]<=plane;ip=previous[2]>=plane if lower else previous[2]<=plane
                if ic!=ip:
                    fraction=(plane-previous[2])/(current[2]-previous[2]);newp.append(previous+fraction*(current-previous));newn.append(np_+fraction*(nc-np_))
                if ic:newp.append(current);newn.append(nc)
            points,attributes=newp,newn
        for j in range(1,len(points)-1):qs.append(np.array([[points[0],points[j],points[j+1]]]));ns.append(np.array([[attributes[0],attributes[j],attributes[j+1]]]))
    return np.ascontiguousarray(np.concatenate(qs)),np.ascontiguousarray(np.concatenate(ns))

def render_one(mesh,camera,appearance):
    mesh=prepare_mesh(mesh,appearance.get('shading','smooth'));selection=camera.get('mesh','ambas');arches=list(mesh['arches']) if selection=='ambas' else [selection]
    if any(a not in mesh['arches'] for a in arches):raise ValueError('Arcada solicitada ausente')
    triangles=np.concatenate([mesh['arches'][a]['triangles'] for a in arches]);normals=np.concatenate([mesh['arches'][a]['normals'] for a in arches]);pos,basis=camera_basis(camera)
    resolution=camera['resolution'];w,h=map(int,resolution)
    if w<8 or h<8 or w*h>32_000_000:raise ValueError('Resolução fora do limite')
    ss=int(appearance.get('supersampling',1))
    if ss not in (1,2,3,4):raise ValueError('supersampling deve ser 1..4')
    W,H=w*ss,h*ss;near=float(camera.get('near',.01));far=float(camera.get('far',10000))
    if not 0<near<far:raise ValueError('Clipping exige 0 < near < far')
    q,normal_camera=_clip_depth((triangles-pos)@basis,normals@basis,near,far);z=np.ascontiguousarray(q[:,:,2]);perspective=camera['projection']=='perspective'
    if camera['projection'] not in ('orthographic','perspective'):raise ValueError('Projeção inválida')
    if perspective:
        fov=float(camera['fov_y_deg'])
        if not 1<fov<175:raise ValueError('FOV inválido')
        scale=H/(2*np.tan(np.deg2rad(fov)/2));den=np.where(abs(z)<1e-12,1e-12,z);x=q[:,:,0]/den*scale+W/2;y=H/2-q[:,:,1]/den*scale
    else:
        extent=float(camera['ortho_height'])
        if extent<=0:raise ValueError('Extensão ortográfica inválida')
        x=q[:,:,0]*H/extent+W/2;y=H/2-q[:,:,1]*H/extent
    pixels=np.ascontiguousarray(np.stack([x,y],axis=-1));normal_camera=np.ascontiguousarray(normal_camera);background=np.asarray(camera.get('background',appearance['background']),float);material=np.asarray(appearance['material_rgb'],float);light=np.asarray(appearance['light_direction_camera'],float)
    if np.linalg.norm(light)<1e-9:raise ValueError('Luz inválida')
    light=light/np.linalg.norm(light)
    image,depth=_raster(pixels,z,normal_camera,W,H,perspective,float(camera.get('near',.01)),float(camera.get('far',10000)),background,material,float(appearance['ambient']),float(appearance['diffuse']),light,bool(appearance.get('two_sided',True)))
    mask=np.isfinite(depth)
    if ss>1:
        image=np.asarray(Image.fromarray(image).resize((w,h),Image.Resampling.LANCZOS));mask=mask.reshape(h,ss,w,ss).any(axis=(1,3))
    return image,mask

def render_views(mesh,camera_config):
    """Retorna dict nome→RGB uint8; recusa configuração de treino não calibrada."""
    cfg=json.loads(Path(camera_config).read_text()) if isinstance(camera_config,(str,Path)) else camera_config
    if cfg.get('status') not in ('CALIBRATED','STANDARDIZED_STL') and not cfg.get('allow_uncalibrated',False):raise ValueError('Câmeras PLACEHOLDER: calibração de treino não confirmada; usar configuração experimental explicitamente para demonstrações')
    if set(cfg.get('views',{}))!=set(VIEWS):raise ValueError('As seis vistas exatas são obrigatórias')
    prepared=prepare_mesh(mesh,cfg['appearance'].get('shading','smooth'))
    return {name:render_one(prepared,cfg['views'][name],cfg['appearance'])[0] for name in VIEWS}
