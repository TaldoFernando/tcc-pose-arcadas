"""Decompõe as 292 falhas com início conhecido da Etapa 2; não altera refinamentos."""
from common import *
from replay import perturb
from anatomical_pair import run_icp,anatomical_frame
from pca_pair import reference
from scipy.spatial.transform import Rotation

def main():
    assert (OUT/'congelamento.json').exists()
    rows=[r for r in csv.DictReader((OUT/'referencias/diagnostico_etapa2.csv').open()) if r['classificacao_operacional']=='DESVIO_MESMO_INICIALIZANDO_NO_ORACULO'];assert len(rows)==292
    baselines={r['id']:r for r in load_json('referencias/baselines_etapa2.json')};pairs={p['id']:p for p in load_json('pares.json')}
    tu=sample_surface(read_triangles(OUT/'referencias/template2_superior.stl'),2048,SEED+1);tl=sample_surface(read_triangles(OUT/'referencias/template2_inferior.stl'),2048,SEED+2);origin=(tu.mean(0)+tl.mean(0))/2;F,_=anatomical_frame(tu,tl,1.,'pca_sign')
    output=[]
    for row in rows:
        (u,l),Q,shift,_,_=perturb(pairs[row['id']],int(row['ensaio'])-1);method=row['metodo'];source=reference(u,l,method);target=reference(tu-origin,tl-origin,method)
        base=baselines[row['id']]['metodos'][method];expected=np.array(base['R'])@Q.T;t=np.array(base['t'])-expected@shift;init=np.eye(4);init[:3,:3]=expected;init[:3,3]=t
        result=run_icp(source,target,init);D=np.array(result['R'])@expected.T;vec=np.rad2deg(Rotation.from_matrix(F.T@D@F).as_rotvec());error=geodesic_deg(D)
        assert np.isclose(error,float(row['erro_ICP_inicializado_oraculo']),atol=1e-5)
        output.append({'id':row['id'],'subset':row['subset'],'method_etapa2':method,'trial':row['ensaio'],'error_deg':error,'lateral_deg':float(vec[0]),'AP_deg':float(vec[1]),'vertical_deg':float(vec[2]),'dominant_axis':['lateral','AP','vertical'][int(np.argmax(np.abs(vec)))],'frame':'template Etapa 2 P063, frame geométrico da regra congelada Etapa 3'})
    save_csv('resultados/oraculos292_componentes.csv',output);save_json('resultados/frame_oraculos.json',{'frame_columns':F.tolist(),'axes':['lateral','AP','vertical'],'template':'P063, histórico Etapa 2; não usado como template nos refinamentos novos'})
    print('292 oráculos reexecutados e decompostos.')
if __name__=='__main__':main()
