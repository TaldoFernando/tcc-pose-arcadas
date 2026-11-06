from common import *
from replay import *
from avaliar import gate_score
from PIL import Image

def main():
    trials=[r for r in load_json('teste/ensaios.json') if r['method']=='anatomica'];pairs={p['id']:p for p in load_json('pares.json')};gate=load_json('porta_qualidade.json')
    maxima=[]
    for identifier in sorted({r['id'] for r in trials}):maxima.append(max([r for r in trials if r['id']==identifier],key=lambda r:r['error_deg']))
    maxima.sort(key=lambda r:r['error_deg'],reverse=True);selected=[];seen=set()
    for row in maxima:
        p=pairs[row['id']];h=(p['superior']['sha256'],p['inferior']['sha256'])
        if h not in seen:selected.append(row);seen.add(h)
        if len(selected)==10:break
    table=[];images=[]
    for rank,r in enumerate(selected,1):
        p=pairs[r['id']];Q=np.array(r['Q']);u=np.array(r['u']);R=np.array(r['result']['R']);t=np.array(r['result']['t']);composed={'R':(R@Q).tolist(),'t':(R@u+t).tolist()}
        tri=[np.load(OUT/'cache'/r['id']/f'{a}_preview.npz')['tri'] for a in ['superior','inferior']]
        score=gate_score(r['result'],gate);path=f'revisao/{rank:02d}_{r["id"]}_ensaio{r["trial"]:02d}.png'
        title=f'{rank}. {r["id"]}, teste, ensaio {r["trial"]}, erro={r["error_deg"]:.2f} graus, revisar={score>=gate["threshold"]}'
        preview_pair(*tri,path,title,composed);images.append(path)
        table.append({'rank':rank,'id':r['id'],'paciente':p['paciente'],'ensaio':r['trial'],'erro_graus':r['error_deg'],'score_porta':score,'revisar_manualmente':score>=gate['threshold'],'PNG':path,'nota':'malhas completas na pose estimada de dados perturbados; pontos foram recortados/ruidosos, malhas exibidas não'})
    save_csv('revisao/piores10_teste.csv',table)
    for k in range(2):
        canvas=Image.new('RGB',(1560,2600),'white')
        for j,path in enumerate(images[k*5:(k+1)*5]):canvas.paste(Image.open(OUT/path).convert('RGB'),(0,j*520))
        canvas.save(OUT/'revisao'/f'folha_{k+1:02d}.png')
    canvas=Image.new('RGB',(2340,1950),'white')
    for j,path in enumerate(images):
        im=Image.open(OUT/path).convert('RGB');im.thumbnail((1170,390));canvas.paste(im,((j%2)*1170,(j//2)*390))
    canvas.save(OUT/'revisao/contato_10.png')
    print('10 piores pares únicos do teste, PNG individuais e duas folhas gerados.')
if __name__=='__main__':main()
