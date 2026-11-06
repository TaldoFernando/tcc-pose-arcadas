from common import *
from replay import baseline_points
from refinements import Target,refine,rigid_fit
from anatomical_pair import normalize_anatomical
from executar import estimate,load_targets
from replay import perturb
from scipy.spatial.transform import Rotation

def main():
    frozen=load_json('congelamento.json');split=load_json('divisao.json');pairs=load_json('pares.json');selected=load_json('escolhas.json')['selected']
    for path,h in frozen['hashes'].items():assert digest(OUT/path)==h,path
    for entry in load_json('templates/selecao.json'):assert entry['id'] in split['desenvolvimento']
    integrity=[]
    for r in load_json('manifesto_copias.json'):
        valid=digest(OUT/r['copia'])==digest(r['fonte'])==digest(r['original'])==r['sha256'];assert valid;integrity.append({'id':r['id'],'arcada':r['arcada'],'intacto':True})
    save_json('integridade.json',integrity)
    for subset,n in [('desenvolvimento',20),('teste',49)]:
        rows=load_json(subset+'/ensaios.json');methods=load_json('plano_preteste.json')['variants'] if subset=='desenvolvimento' else selected
        assert len(rows)==n*20*len(methods)
        assert not any(r['result'].get('invalid',False) for r in rows),'Há resultados numéricos inválidos: reportar explicitamente'
        old={(r['id'],r['trial']):r for r in load_json('referencias/'+subset+'/ensaios.json') if r['method']=='anatomica'}
        for r in rows:
            assert np.allclose(r['Q'],old[(r['id'],r['trial'])]['Q']);assert np.allclose(r['u'],old[(r['id'],r['trial'])]['u'])
            R=np.array(r['result']['R']);assert np.allclose(R.T@R,np.eye(3),atol=1e-7) and np.isclose(np.linalg.det(R),1)
    p=next(p for p in pairs if p['id']==split['desenvolvimento'][0]);u,l=baseline_points(p);primary=np.load(OUT/'templates/P016.npz');target=Target(primary['upper'],primary['lower']);new=refine(u,l,target,'point_point');old=normalize_anatomical(u,l,primary['upper'],primary['lower'],1.,'pca_sign')
    assert np.allclose(new['R'],old['R'],atol=1e-7);assert np.allclose(new['t'],old['t'],atol=1e-7)
    # Conferência serial de uma consulta que foi processada em worker no teste.
    probe=next(p for p in pairs if p['id']==split['teste'][0]);(pu,pl),Q,shift,_,_=perturb(probe,0);repeated=estimate(pu,pl,load_targets(),selected)
    saved=[r for r in load_json('teste/ensaios.json') if r['id']==probe['id'] and r['trial']==1]
    for row in saved:
        assert np.allclose(row['result']['R'],repeated[row['method']]['R'],atol=1e-7)
        assert np.allclose(row['result']['t'],repeated[row['method']]['t'],atol=1e-7)
    rng=np.random.default_rng(23);a=rng.normal(size=(80,3));R0=Rotation.from_rotvec([.2,-.4,.1]).as_matrix();t0=np.array([4,-3,2]);R,t=rigid_fit(a,a@R0.T+t0);assert np.allclose(R,R0) and np.allclose(t,t0)
    rows=list(csv.DictReader((OUT/'resultados/componentes_rotacao.csv').open()))
    for r in rows:
        norm=np.linalg.norm([float(r[k]) for k in ['lateral_deg','AP_deg','vertical_deg']]);assert np.isclose(norm,float(r['error_deg']),atol=1e-4)
    assert len(list(csv.DictReader((OUT/'resultados/oraculos292_componentes.csv').open())))==292
    assert load_json('divisao.json')==json.loads((ROOT/'etapa3/divisao.json').read_text())
    assert all('PLACEHOLDER' in str(v) for cam in json.loads((ROOT/'config.json').read_text())['cameras'].values() for v in cam.values())
    print('OK: 138 fontes/cópias/originais intactos, congelamento íntegro, templates só dev, mesma divisão e Q/u, SO(3), ponto-a-ponto reproduz Etapa 3, Kabsch sintético, norma dos componentes, 292 oráculos, câmeras PLACEHOLDER. Porta não reajustada nem aplicada.')
if __name__=='__main__':main()
