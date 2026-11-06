from pathlib import Path
import sys,json,copy,hashlib
import numpy as np
OUT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(OUT))
from render_views import prepare_mesh,render_one,render_views,_raster,_clip_depth
from metrics import compare_images

def main():
 square=np.array([[[-1,-1,0],[1,-1,0],[1,1,0]],[[-1,-1,0],[1,1,0],[-1,1,0]]],float);mesh=prepare_mesh({'superior':square});c={'projection':'orthographic','position':[0,0,5],'target':[0,0,0],'up':[0,1,0],'resolution':[128,128],'ortho_height':4,'near':.1,'far':100,'mesh':'superior','background':[0,0,0]};a={'background':[0,0,0],'material_rgb':[255,255,255],'ambient':1,'diffuse':0,'light_direction_camera':[0,0,-1],'supersampling':1,'shading':'smooth'}
 im,mask=render_one(mesh,c,a);check={};check['known_orthographic_area']=int(mask.sum())==4096;metrics=compare_images(im,im,mask,mask);check['identity_metrics']=metrics['IoU']==1 and metrics['SSIM']==1 and metrics['centroid_px']==0 and metrics['scale_percent']==0
 c2=copy.deepcopy(c);c2['position']=[0,0,50];im2,m2=render_one(mesh,c2,a);check['orthographic_distance_gauge']=np.array_equal(im,im2)
 c3=copy.deepcopy(c);c3['position']=[1,0,5];c3['target']=[1,0,0];im3,m3=render_one(mesh,c3,a);check['known_translation_32px']=abs(compare_images(im3,im,m3,mask)['centroid_px']-32)<1e-9
 c4=copy.deepcopy(c);c4['ortho_height']=8;_,m4=render_one(mesh,c4,a);check['known_scale_area_quarter']=int(m4.sum())==1024
 c5=copy.deepcopy(c);c5['projection']='perspective';c5['fov_y_deg']=90;_,m5=render_one(mesh,c5,a);check['perspective_scale']=int(m5.sum())==26*26
 rejected=False
 try:render_views({'superior':square},{'status':'PLACEHOLDER','allow_uncalibrated':False})
 except ValueError:rejected=True
 check['placeholder_default_rejected']=rejected
 pixels=np.array([[[0,0],[63,0],[0,63]],[[0,0],[63,0],[0,63]]],float);z=np.array([[1,1,1],[2,2,2]],float);normals=np.array([[[0,0,-1]]*3,[[1,0,0]]*3],float)
 img,_=_raster(pixels,z,normals,64,64,False,.1,100,np.array([0.,0.,0.]),np.array([255.,255.,255.]),0.,1.,np.array([0.,0.,-1.]),True);check['z_buffer_near_surface_occludes_far']=bool(np.all(img[10,10]==255))
 q=np.array([[[0,0,0],[1,0,2],[0,1,2]]],float);normals=np.tile([[[0,0,1]]],(1,3,1));clipped,_=_clip_depth(q,normals,1,3);check['near_plane_clipping']=len(clipped)==2 and bool(np.all(clipped[:,:,2]>=1))
 input_hash=hashlib.sha256(square.tobytes()).hexdigest();render_one(mesh,c,a);check['input_not_mutated']=input_hash==hashlib.sha256(square.tobytes()).hexdigest();check['synthetic_unit_tests_only_not_training_validation']=True
 (OUT/'resultados/testes_render.json').write_text(json.dumps(check,indent=2));assert all(check.values()),'Teste falhou; conferir relatório sem nomes';print('RENDER TESTS PASS',len(check),'no training validation claimed')
if __name__=='__main__':main()
