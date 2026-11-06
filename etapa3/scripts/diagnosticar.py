"""Oráculo de CONSISTÊNCIA conhecido; não é oráculo de correção anatômica."""
from common import *
from replay import *
from anatomical_pair import run_icp
from pca_pair import reference
import time

def main():
    assert (OUT/'congelamento.json').exists(),'Diagnóstico do teste só após congelar regras e porta'
    original=load_json('referencia_etapa2/normalizacoes.json');bybase={r['id']:r for r in original};pairs=load_json('pares.json');split=load_json('divisao.json')
    rows=list(csv.DictReader((OUT/'referencia_etapa2/ensaios.csv').open()));failures=[r for r in rows if float(r['erro_angular_graus'])>5]
    tu=sample_surface(read_triangles(OUT/'referencia_etapa2/template_superior.stl'),2048,SEED+1);tl=sample_surface(read_triangles(OUT/'referencia_etapa2/template_inferior.stl'),2048,SEED+2);origin=(tu.mean(0)+tl.mean(0))/2
    output=[]
    for idx,p in enumerate(pairs):
        start=time.time();these=[r for r in failures if r['id']==p['id']]
        for k in sorted({int(r['ensaio']) for r in these}):
            (u,l),Q,shift,seed,meta=perturb(p,k-1)
            for old in [r for r in these if int(r['ensaio'])==k]:
                method=old['metodo'];source=reference(u,l,method);target=reference(tu-origin,tl-origin,method)
                result=normalize_points(source,target);chosen=result['candidate']
                assert np.allclose(result['R'],json.loads(old['R']),atol=1e-7),'Replay divergiu'
                assert np.allclose(Q,json.loads(old['Q'])) and np.allclose(shift,json.loads(old['u']))
                base=bybase[p['id']]['metodos'][method];R0=np.array(base['R']);t0=np.array(base['t']);expectedR=R0@Q.T;expectedt=t0-expectedR@shift
                cs,As,_=center_pca(source);ct,At,_=center_pca(target)
                initials=[geodesic_deg(At@S@As.T@expectedR.T) for S in SIGNS]
                errors=[geodesic_deg(np.array(c['R'])@expectedR.T) for c in result['candidates']]
                passing=[i for i,e in enumerate(errors) if e<=5];nearest=int(np.argmin(initials));best=int(np.argmin(errors))
                init=np.eye(4);init[:3,:3]=expectedR;init[:3,3]=expectedt;oracle=run_icp(source,target,init);oe=geodesic_deg(np.array(oracle['R'])@expectedR.T)
                if passing:cause='SELECAO_RMSE_OUTRO_CANDIDATO_CONSISTENTE'
                elif oe<=5 and min(initials)>30:cause='PCA_GROSSEIRA_E_BACIA_ICP'
                elif oe<=5:cause='BACIA_LOCAL_ICP'
                else:cause='DESVIO_MESMO_INICIALIZANDO_NO_ORACULO'
                output.append({'id':p['id'],'subset':'dev' if p['id'] in split['desenvolvimento'] else 'test','metodo':method,'ensaio':k,'erro_escolhido':errors[chosen],'candidato_escolhido':chosen,'sinais_escolhidos':json.dumps(np.diag(SIGNS[chosen]).tolist()),'candidato_inicial_mais_proximo_oraculo':nearest,'erro_inicial_mais_proximo':min(initials),'candidatos_finais_consistentes_ate5':json.dumps(passing) if passing else 'NENHUM','candidato_final_menor_erro':best,'menor_erro_final':min(errors),'erros_iniciais_4':json.dumps(initials),'erros_finais_4':json.dumps(errors),'RMSE_4':json.dumps([c['RMSE'] for c in result['candidates']]),'erro_ICP_inicializado_oraculo':oe,'RMSE_ICP_oraculo':oracle['RMSE'],'classificacao_operacional':cause,'nota':'correto refere-se à normalização baseline e Q conhecida, não à anatomia'})
        if output:save_csv('resultados/diagnostico_falhas_etapa2.csv',output)
        print(idx+1,len(pairs),p['id'],'falhas',len(these),f'{time.time()-start:.1f}s',flush=True)
    assert len(output)==len(failures)==1104
    print('DIAGNOSTICO_CONCLUIDO',flush=True)
if __name__=='__main__':main()
