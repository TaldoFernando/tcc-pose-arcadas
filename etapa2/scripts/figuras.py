"""Previews locais para orientadora; não são vistas/câmeras de treino."""
from common import *
from PIL import Image,ImageDraw

def contact(files,path,columns=1,thumb_width=1560):
    ims=[]
    for p in files:
        im=Image.open(OUT/p).convert('RGB');im.thumbnail((thumb_width,int(thumb_width/3)));ims.append(im)
    h=max(im.height for im in ims);canvas=Image.new('RGB',(columns*thumb_width,((len(ims)+columns-1)//columns)*h),'white')
    for i,im in enumerate(ims):canvas.paste(im,((i%columns)*thumb_width,(i//columns)*h))
    canvas.save(OUT/path)

def main():
    pairs=load_json('pares.json');byid={p['id']:p for p in pairs};selection=load_json('selecao_visual.json');baselines={p['id']:p for p in load_json('resultados/normalizacoes.json')} if (OUT/'resultados/normalizacoes.json').exists() else {}
    originals=[];normalized=[]
    for category,ids in [('originais',selection['originais_15']),('normalizados',selection['normalizados_20'])]:
        for identifier in ids:
            p=byid[identifier]
            if category=='normalizados' and identifier not in baselines:continue
            tri=[np.load(OUT/'cache'/identifier/f'{a}_preview.npz')['tri'] for a in ['superior','inferior']]
            if category=='originais':path=f'previews_originais/{identifier}.png';result=None;originals.append(path)
            else:path=f'revisao_normalizados/{identifier}.png';result=baselines[identifier]['metodos']['combinada'];normalized.append(path)
            if not (OUT/path).exists():preview_pair(*tri,path=path,title=f'{identifier} — {category} | {p["status_articulacao"]}'+(' | referência combinada' if result else ''),transformation=result)
            print('PNG',path,flush=True)
    if len(originals)==15:contact(originals,'previews_originais/contato_15.png',columns=3,thumb_width=780)
    if len(normalized)==20:contact(normalized,'revisao_normalizados/contato_20.png',columns=2,thumb_width=1200)
    for k in range(4):
        if len(normalized)>=5*(k+1):contact(normalized[k*5:(k+1)*5],f'revisao_normalizados/folha_{k+1:02d}.png')
    if (OUT/'resultados/comparacao_metodos.csv').exists():
        for row in csv.DictReader((OUT/'resultados/comparacao_metodos.csv').open()):
            for method in ['superior','combinada']:
                if float(row['rotacao_aplicada_'+method+'_graus'])>90:
                    identifier=row['id'];tri=[np.load(OUT/'cache'/identifier/f'{a}_preview.npz')['tri'] for a in ['superior','inferior']]
                    preview_pair(*tri,path=f'revisao_normalizados/ALERTA_{identifier}_{method}.png',title=f'REVISAR {identifier} — {method} — rotação aplicada >90 graus',transformation=baselines[identifier]['metodos'][method])
    print('FIGURAS_CONCLUIDAS',flush=True)
if __name__=='__main__':main()
