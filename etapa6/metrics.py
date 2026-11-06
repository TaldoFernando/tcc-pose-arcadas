"""Métricas locais. Máscara por fundo é heurística, não anotação manual."""
import numpy as np
import cv2
from skimage.metrics import structural_similarity

def estimate_background(image):
    image=np.asarray(image)[:,:,:3];h,w=image.shape[:2];n=max(2,int(round(min(h,w)*.025)))
    corners=np.concatenate([image[:n,:n].reshape(-1,3),image[:n,-n:].reshape(-1,3),image[-n:,:n].reshape(-1,3),image[-n:,-n:].reshape(-1,3)])
    return np.median(corners,axis=0)

def foreground(image,background=None,threshold=12):
    image=np.asarray(image)[:,:,:3].astype(float);bg=estimate_background(image) if background is None else np.asarray(background,float);mask=np.max(abs(image-bg),axis=2)>threshold
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8);keep=np.zeros(count,bool)
    if count>1:keep[1:]=stats[1:,cv2.CC_STAT_AREA]>=max(8,int(mask.size*.00005))
    return keep[labels]

def geometry(mask):
    y,x=np.nonzero(mask)
    if not len(x):return None
    return {'centroid':np.array([x.mean()+.5,y.mean()+.5]),'bbox':np.array([x.min(),y.min(),x.max()+1,y.max()+1]),'area':len(x)}

def compare_images(render,reference,render_mask=None,reference_mask=None):
    a=np.asarray(render)[:,:,:3];b=np.asarray(reference)[:,:,:3]
    if a.shape!=b.shape:raise ValueError('Resoluções diferentes: não redimensionar silenciosamente')
    ma=foreground(a) if render_mask is None else np.asarray(render_mask,bool);mb=foreground(b) if reference_mask is None else np.asarray(reference_mask,bool);ga=geometry(ma);gb=geometry(mb)
    iou=float(np.sum(ma&mb)/max(1,np.sum(ma|mb)));ssim=float(structural_similarity(a,b,channel_axis=2,data_range=255));mse=float(np.mean((a.astype(float)-b.astype(float))**2))
    if ga is None or gb is None:return {'IoU':iou,'SSIM':ssim,'centroid_px':float('nan'),'scale_percent':float('nan'),'signed_scale_percent':float('nan'),'bbox_size_error_percent':float('nan'),'bbox_error_px':float('nan'),'MSE':mse,'empty_mask':True}
    wa,ha=ga['bbox'][2:]-ga['bbox'][:2];wb,hb=gb['bbox'][2:]-gb['bbox'][:2];ratio=np.sqrt(wa*ha/(wb*hb));delta=ga['bbox']-gb['bbox']
    return {'IoU':iou,'SSIM':ssim,'centroid_px':float(np.linalg.norm(ga['centroid']-gb['centroid'])),'scale_percent':float(abs(ratio-1)*100),'signed_scale_percent':float((ratio-1)*100),'bbox_size_error_percent':float(max(abs(wa/wb-1),abs(ha/hb-1))*100),'bbox_error_px':float(np.sqrt(np.mean(delta*delta))),'MSE':mse,'empty_mask':False}

def objective(metrics,shape):
    if metrics['empty_mask']:return 100.
    diagonal=np.linalg.norm(shape[:2]);return (1-metrics['IoU'])+.25*(1-metrics['SSIM'])+metrics['centroid_px']/diagonal+.25*metrics['bbox_error_px']/diagonal+.25*metrics['scale_percent']/100
