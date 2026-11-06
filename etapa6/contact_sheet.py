"""Folha pareada somente com referências locais verificadas pelo chamador.

Referências com texto identificável precisam de cópia redigida para divulgação;
as métricas são calculadas nas imagens originais, não na folha anotada.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_views import render_one,VIEWS

def make_contact_sheet(records,config,path,seed=20261106,count=10):
    if len(records)<count:raise ValueError('Menos de dez IDs pareados: não fabricar referências ou diferenças')
    if any(not r.get('confirmed_pair') or not r.get('confirmed_training_source') for r in records):raise ValueError('Pareamento e origem não confirmados')
    chosen=np.random.default_rng(seed).choice(len(records),count,replace=False);cw=120;rh=150;left=65;top=65;sheet=Image.new('RGB',(left+18*cw,top+count*rh),'white');draw=ImageDraw.Draw(sheet)
    for j,view in enumerate(VIEWS):
        draw.text((left+j*3*cw,10),view,fill='black')
        for k,label in enumerate(['render','treino','abs diferenca x4']):draw.text((left+(3*j+k)*cw,30),label,fill='black')
    IDs=[]
    for row,idx in enumerate(chosen):
        r=records[idx];IDs.append(r['ID']);y=top+row*rh;draw.text((3,y+10),r['ID'],fill='black')
        for j,view in enumerate(VIEWS):
            render,_=render_one(r['_mesh'],config['views'][view],config['appearance']);reference=np.asarray(Image.open(r['images'][view]).convert('RGB'))
            if render.shape!=reference.shape:raise ValueError('Resoluções diferentes; sem resize silencioso')
            difference=np.clip(np.abs(render.astype(float)-reference.astype(float))*4,0,255).astype(np.uint8)
            for k,image in enumerate([render,reference,difference]):
                cell=Image.fromarray(image);cell.thumbnail((cw-4,rh-10));sheet.paste(cell,(left+(3*j+k)*cw,y))
    sheet.save(Path(path));return IDs
