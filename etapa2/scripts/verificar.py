"""Verificações de transformação comum, cobertura e preservação dos arquivos."""
from common import *
from scipy.spatial.transform import Rotation
from scipy.spatial.distance import cdist
import collections

def main():
    pairs=load_json('pares.json');base=load_json('resultados/normalizacoes.json');trials=list(csv.DictReader((OUT/'resultados/robustez_ensaios.csv').open()))
    assert len(pairs)==len(base)==69
    counts=collections.Counter((r['id'],r['metodo']) for r in trials)
    assert len(trials)==2760 and len(counts)==138 and set(counts.values())=={20}
    point_seeds=[]
    for r in trials:
        Q=np.array(json.loads(r['Q']));R=np.array(json.loads(r['R']))
        assert np.allclose(Q.T@Q,np.eye(3),atol=1e-8) and np.isclose(np.linalg.det(Q),1)
        assert np.allclose(R.T@R,np.eye(3),atol=1e-8) and np.isclose(np.linalg.det(R),1)
        for m in json.loads(r['perturbacoes']):
            assert .099<=m['crop']['fraction']<=.301
            assert 1400<=m['pontos_restantes']<=1850
            point_seeds.append(m['seed_amostragem'])
        assert np.isfinite(float(r['erro_angular_graus'])) and np.isfinite(float(r['RMSE']))
    rng=np.random.default_rng(SEED);u=rng.normal(size=(80,3))*[20,12,5];l=rng.normal(size=(80,3))*[20,12,4]+[0,2,-12]
    Q=Rotation.from_euler('xyz',[131,71,-113],degrees=True).as_matrix();t=np.array([51,7,-83])
    for method in ['superior','combinada']:
        baseline=normalize_pair_points(u,l,u,l,method);moved=normalize_pair_points(apply_transform(u,Q,t),apply_transform(l,Q,t),u,l,method)
        err=geodesic_deg(np.array(moved['R'])@Q@np.array(baseline['R']).T);assert err<1e-3
        assert np.linalg.norm(np.array(moved['R'])@t+np.array(moved['t'])-np.array(baseline['t']))<1e-5
    from pose_normalize_pair import normalize_pair
    first=pairs[0];first_baseline=next(b for b in base if b['id']==first['id'])
    for method in ['superior','combinada']:
        public=normalize_pair(OUT/first['superior']['arquivo'],OUT/first['inferior']['arquivo'],OUT/'templates/superior.stl',OUT/'templates/inferior.stl',method)
        assert np.allclose(public['R'],first_baseline['metodos'][method]['R'],atol=1e-10)
        assert np.allclose(public['t'],first_baseline['metodos'][method]['t'],atol=1e-10)
    invariance=[]
    for b in base:
        p=next(p for p in pairs if p['id']==b['id'])
        us=sample_surface(read_triangles(OUT/p['superior']['arquivo']),32,SEED);ls=sample_surface(read_triangles(OUT/p['inferior']['arquivo']),32,SEED+1)
        before=cdist(us,ls)
        for method,r in b['metodos'].items():
            for c in r['candidates']:
                R=np.array(c['R']);assert np.allclose(R.T@R,np.eye(3),atol=1e-8) and np.isclose(np.linalg.det(R),1)
            after=cdist(apply_transform(us,r['R'],r['t']),apply_transform(ls,r['R'],r['t']))
            error=float(np.max(np.abs(after-before)));assert error<1e-8
            invariance.append({'id':b['id'],'metodo':method,'max_erro_distancias_entre_arcadas':error})
    save_csv('resultados/invariancia_articulacao.csv',invariance)
    integrity=[]
    for r in load_json('manifesto_copias.json'):
        valid=digest(OUT/r['copia'])==digest(r['fonte'])==digest(r['original'])==r['sha256'];assert valid
        integrity.append({'id':r['id'],'categoria':r['categoria'],'copia_fonte_original_inalterados':valid,'sha256':r['sha256']})
    save_json('validacao_integridade.json',integrity)
    selection=load_json('selecao_visual.json')
    for identifier in selection['originais_15']:assert (OUT/'previews_originais'/f'{identifier}.png').is_file()
    for identifier in selection['normalizados_20']:assert (OUT/'revisao_normalizados'/f'{identifier}.png').is_file()
    for k in range(1,5):assert (OUT/'revisao_normalizados'/f'folha_{k:02d}.png').is_file()
    print('OK: 69 pares, 2 métodos, 2.760 ensaios; SO(3), composição de pose conhecida, distância entre arcadas preservada, fontes/cópias intactas, 15+20 PNG e 4 folhas. Câmeras de treino não usadas.')
if __name__=='__main__':main()
