"""20 ensaios independentes por par, com todas as perturbações simultâneas."""
from common import *
from scipy.spatial.transform import Rotation
import time
METHODS=['superior','combinada']

def spatial_crop(points,rng):
    fraction=float(rng.uniform(.10,.30));anchor=int(rng.integers(len(points)));d=np.linalg.norm(points-points[anchor],axis=1)
    count=int(round(len(points)*fraction));order=np.argsort(d,kind='stable');keep=np.ones(len(points),bool);keep[order[:count]]=False
    return points[keep],{'fraction':count/len(points),'anchor':points[anchor].tolist(),'radius':float(d[order[count-1]])}

def main():
    pairs=load_json('pares.json');selection=load_json('templates/selecao.json');template_id=selection['id']
    tu=sample_surface(read_triangles(OUT/'templates/superior.stl'),2048,SEED+1);tl=sample_surface(read_triangles(OUT/'templates/inferior.stl'),2048,SEED+2)
    baselines=[];trials=[]
    if (OUT/'resultados/normalizacoes.json').exists():baselines=load_json('resultados/normalizacoes.json')
    if (OUT/'resultados/robustez_ensaios.csv').exists():trials=list(csv.DictReader((OUT/'resultados/robustez_ensaios.csv').open()))
    done={r['id'] for r in baselines if sum(x['id']==r['id'] for x in trials)==40}
    for idx,p in enumerate(pairs):
        if p['id'] in done:continue
        started=time.time();identifier=p['id'];cache=OUT/'cache'/identifier
        upper=read_triangles(OUT/p['superior']['arquivo']);lower=read_triangles(OUT/p['inferior']['arquivo'])
        us=sample_surface(upper,2048,SEED+11);ls=sample_surface(lower,2048,SEED+12)
        results={method:normalize_pair_points(us,ls,tu,tl,method) for method in METHODS}
        # Mesmos R/t em ambas as arcadas conservam todas as distâncias relativas.
        baseline={'id':identifier,'paciente':p['paciente'],'parece_articulado':p['parece_articulado'],'template':template_id,'metodos':results}
        errors={m:[] for m in METHODS}
        for k in range(20):
            seed=SEED+1000*(idx+1)+k;rng=np.random.default_rng(seed);Q=Rotation.random(random_state=rng).as_matrix();shift=rng.uniform(-100,100,3)
            perturbed=[];metadata=[]
            for category in ['superior','inferior']:
                level=str(rng.choice(['leve','forte']));tri=np.load(cache/f'{category}_{level}.npz')['tri'];point_seed=int(rng.integers(1,2**31))
                # Decimações em cache são geometricamente distintas do STL baseline.
                # Amostragem, ruído e recorte são refeitos independentemente em cada ensaio.
                pts=sample_surface(tri,2048,point_seed);pts=apply_transform(pts,Q,shift);pts+=rng.normal(0,.15,pts.shape)
                pts,crop=spatial_crop(pts,rng);perturbed.append(pts)
                metadata.append({'arcada':category,'seed_amostragem':point_seed,'nivel_decimacao':level,'triangulos_decimados':len(tri),'crop':crop,'pontos_restantes':len(pts)})
            for method in METHODS:
                result=normalize_pair_points(*perturbed,tu,tl,method);R1=np.array(result['R']);t1=np.array(result['t']);R0=np.array(results[method]['R']);t0=np.array(results[method]['t'])
                error=geodesic_deg((R1@Q)@R0.T);t_error=float(np.linalg.norm(R1@shift+t1-t0));errors[method].append(error)
                trials.append({'id':identifier,'metodo':method,'ensaio':k+1,'seed':seed,'parece_articulado':p['parece_articulado'],'erro_angular_graus':error,'erro_translacao':t_error,'falha_maior_5_graus':error>5,'RMSE':result['RMSE'],'fitness':result['fitness'],'Q':json.dumps(Q.tolist()),'u':json.dumps(shift.tolist()),'R':json.dumps(result['R']),'t':json.dumps(result['t']),'perturbacoes':json.dumps(metadata),'sigma_ruido':.15})
        baselines=[r for r in baselines if r['id']!=identifier];baselines.append(baseline)
        save_json('resultados/normalizacoes.json',baselines);save_csv('resultados/robustez_ensaios.csv',trials)
        print(f'{idx+1}/{len(pairs)} {identifier} sup_max={max(errors["superior"]):.3f} combinado_max={max(errors["combinada"]):.3f} tempo={time.time()-started:.1f}s',flush=True)
    save_json('parametros.json',{'seed':SEED,'unidade':'mm ASSUMIDO; sem reescala','pareamento':'pasta + uma superior e uma inferior por conteúdo SHA256; duplicatas explicitadas','articulacao':{'min_aproximado_max':1.5,'bbox_overlap_XY_min':.65,'deslocamento_AP_fracao_max':.25,'deslocamento_lateral_fracao_max':.15,'superior_centroid_Z_maior_inferior':True,'native_axes_assumidos':'X lateral, Y AP, Z vertical; só triagem geométrica'},'icp':{'samples_baseline_por_arcada':2048,'max_iterations':60,'distance':8,'selection':'RMSE simétrico sem corte; quatro sinais próprios PCA'},'robustez':{'trials_por_par_por_metodo':20,'rotacao':'Haar uniforme SO(3)','translacao_uniforme_por_eixo':[-100,100],'sigma_gaussiano':.15,'recorte_fracao_por_arcada':[.10,.30],'recorte':'remove pontos mais próximos de âncora espacial aleatória, independentemente por arcada','nova_amostragem':'uniforme por área, semente independente por arcada/ensaio','decimacao':'quadric Open3D em cópias cache; duas metas: min(30000,max(4000,n_faces * 0.5 ou 0.2)); nível escolhido por arcada/ensaio; cache simplificado antes da transformação rígida','todas_perturbacoes_simultaneas':True,'falha_graus':5},'template':selection,'cameras_treino':'PLACEHOLDER — nenhuma das 6 vistas renderizada','open3d':o3d.__version__})
    print('ROBUSTEZ_CONCLUIDA',flush=True)
if __name__=='__main__':main()
