from common import *
from replay import *
from anatomical_pair import anatomical_frame
from scipy.spatial.transform import Rotation

def main():
    split=load_json('divisao.json');pairs=load_json('pares.json');frozen=load_json('congelamento.json')
    assert len(split['desenvolvimento'])==20 and len(split['teste'])==49
    assert not set(split['desenvolvimento'])&set(split['teste'])
    d={p[a]['sha256'] for p in pairs if p['id'] in split['desenvolvimento'] for a in ['superior','inferior']};t={p[a]['sha256'] for p in pairs if p['id'] in split['teste'] for a in ['superior','inferior']};assert not d&t
    for path,h in frozen['hashes'].items():assert digest(OUT/path)==h,'Modificado depois do congelamento: '+path
    records=[]
    for r in load_json('manifesto_copias.json'):
        pair=next(p for p in pairs if p['id']==r['id']);original=ROOT/'dados'/pair[r['arcada']]['fonte_inventario']
        valid=digest(OUT/r['copia'])==digest(r['fonte'])==digest(original)==r['sha256'];assert valid;records.append({**r,'original':str(original),'intacto':valid})
    save_json('integridade.json',records)
    old=list(csv.DictReader((OUT/'referencia_etapa2/ensaios.csv').open()));byold={(r['id'],int(r['ensaio'])):r for r in old if r['metodo']=='combinada'}
    for folder,n in [('desenvolvimento',20),('teste',49)]:
        data=load_json(folder+'/ensaios.json');assert len(data)==n*20*2
        for row in data:
            assert np.allclose(row['Q'],json.loads(byold[(row['id'],row['trial'])]['Q']))
            assert np.allclose(row['u'],json.loads(byold[(row['id'],row['trial'])]['u']))
            for c in row['result']['candidates']:
                R=np.array(c['R']);assert np.allclose(R.T@R,np.eye(3),atol=1e-8);assert np.isclose(np.linalg.det(R),1)
    rules=load_json('regra.json');p=next(p for p in pairs if p['id'] in split['desenvolvimento']);u,l=baseline_points(p)
    Q=Rotation.from_euler('xyz',[137,-74,112],degrees=True).as_matrix();shift=np.array([53,27,-83])
    F0,_=anatomical_frame(u,l,rules['weight'],rules['vertical_mode']);F1,_=anatomical_frame(u@Q.T+shift,l@Q.T+shift,rules['weight'],rules['vertical_mode']);assert geodesic_deg(F1@F0.T@Q.T)<1e-3
    diagnostics=list(csv.DictReader((OUT/'resultados/diagnostico_falhas_etapa2.csv').open()));assert len(diagnostics)==1104
    assert len(list(csv.DictReader((OUT/'revisao/piores10_teste.csv').open())))==10
    for r in csv.DictReader((OUT/'revisao/piores10_teste.csv').open()):assert r['id'] in split['teste'] and (OUT/r['PNG']).exists()
    assert all('PLACEHOLDER' in str(v) for cam in json.loads((ROOT/'config.json').read_text())['cameras'].values() for v in cam.values())
    print('OK: divisão 20/49 sem STL idêntico cruzando conjuntos; regras/porta/template congelados; 2.760 ensaios novos com mesmas Q/u; candidatos próprios; frame equivarante; 1.104 falhas reexecutadas; 10 piores só do teste; 138 STL íntegros; câmeras PLACEHOLDER.')
if __name__=='__main__':main()
