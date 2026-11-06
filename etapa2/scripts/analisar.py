"""Métricas de robustez e de dispersão entre pacientes; nenhuma validação anatômica."""
from common import *
import collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def stats(v):
    a=np.array(v,dtype=float)
    return {'n':len(a),'min':float(a.min()),'media':float(a.mean()),'desvio_populacional':float(a.std()),'mediana':float(np.median(a)),'max':float(a.max()),'falhas_maior5':int((a>5).sum()),'taxa_falha_maior5':float(np.mean(a>5))}

def main():
    pairs=load_json('pares.json');baselines=load_json('resultados/normalizacoes.json');byid={r['id']:r for r in baselines};template=load_json('templates/selecao.json');trials=list(csv.DictReader((OUT/'resultados/robustez_ensaios.csv').open()))
    summary={};perpair=[];original_pc=next(p for p in pairs if p['id']==template['id'])['superior_axes'];At=np.array(original_pc)
    for method in ['superior','combinada']:
        values=[float(r['erro_angular_graus']) for r in trials if r['metodo']==method]
        summary[method]={'todos_pares':stats(values)}
        seen=set();unique=[]
        for p in pairs:
            h=(p['superior']['sha256'],p['inferior']['sha256'])
            if h not in seen:seen.add(h);unique.append(p['id'])
        summary[method]['pares_unicos']=stats([float(r['erro_angular_graus']) for r in trials if r['metodo']==method and r['id'] in unique])
        summary[method]['pares_unicos_sem_template']=stats([float(r['erro_angular_graus']) for r in trials if r['metodo']==method and r['id'] in unique and r['id']!=template['id']])
        summary[method]['articulados_triagem']=stats([float(r['erro_angular_graus']) for r in trials if r['metodo']==method and r['parece_articulado'] in ['True',True]])
        for p in pairs:
            subset=[r for r in trials if r['id']==p['id'] and r['metodo']==method];v=[float(r['erro_angular_graus']) for r in subset];s=stats(v)
            perpair.append({'id':p['id'],'paciente':p['paciente'],'metodo':method,'parece_articulado':p['parece_articulado'],**s,'RMSE_baseline':byid[p['id']]['metodos'][method]['RMSE']})
        fig,ax=plt.subplots(figsize=(8,4));ax.hist(values,bins=np.linspace(0,180,37),color='#3a80a4');ax.axvline(5,color='#be4930',ls='--',label='Falha >5°');ax.set(xlabel='Erro angular geodésico (°)',ylabel='Ensaios',title=f'Perturbações independentes simultâneas — {method}');ax.legend();fig.tight_layout();fig.savefig(OUT/'resultados'/f'histograma_robustez_{method}.png',dpi=150);plt.close(fig)
    save_json('resultados/robustez_resumo.json',summary);save_csv('resultados/robustez_por_par.csv',perpair)
    # Dispersão sem duplicatas: mesmos pares plausivelmente articulados em todos os métodos.
    eligible=[];seen=set()
    for p in pairs:
        h=(p['superior']['sha256'],p['inferior']['sha256'])
        if p['parece_articulado'] and h not in seen:eligible.append(p);seen.add(h)
    frames={m:{} for m in ['antes','superior','combinada']}
    for p in eligible:
        A=np.array(p['superior_axes']);frames['antes'][p['id']]=A
        for m in ['superior','combinada']:frames[m][p['id']]=np.array(byid[p['id']]['metodos'][m]['R'])@A
    dispersion=[];peer=collections.defaultdict(list)
    for a,b in itertools.combinations(eligible,2):
        r={'id_a':a['id'],'id_b':b['id']}
        for m in frames:
            value=angular_axes(frames[m][a['id']],frames[m][b['id']]);r[m+'_graus']=value;peer[(a['id'],m)].append(value);peer[(b['id'],m)].append(value)
        dispersion.append(r)
    ds={m:{'pacientes_pastas_unicos':len(eligible),'pares':len(dispersion),**stats([r[m+'_graus'] for r in dispersion])} for m in frames}
    for data in ds.values():
        data.pop('falhas_maior5',None);data.pop('taxa_falha_maior5',None)
    save_csv('resultados/dispersao_pares.csv',dispersion);save_json('resultados/dispersao_resumo.json',ds)
    worsen=[]
    for p in eligible:
        a=angular_axes(frames['antes'][p['id']],At);before_peer=float(np.median(peer[(p['id'],'antes')]))
        for method in ['superior','combinada']:
            after=angular_axes(frames[method][p['id']],At);after_peer=float(np.median(peer[(p['id'],method)]))
            worsen.append({'id':p['id'],'paciente':p['paciente'],'metodo':method,'ate_template_antes':a,'ate_template_depois':after,'delta_template_graus':after-a,'piorou_template_mais_0_1grau':after>a+.1,'peer_mediana_antes':before_peer,'peer_mediana_depois':after_peer,'delta_peer_graus':after_peer-before_peer,'piorou_peer_mais_0_1grau':after_peer>before_peer+.1})
    save_csv('resultados/casos_piora.csv',worsen)
    fig,ax=plt.subplots(figsize=(8,4));ax.boxplot([[r[m+'_graus'] for r in dispersion] for m in frames],labels=list(frames),showfliers=True);ax.set(ylabel='Dispersão dos eixos PCA superiores (°)',title='Mesmos pares únicos, quatro sinais próprios PCA');fig.tight_layout();fig.savefig(OUT/'resultados/dispersao_comparacao.png',dpi=150);plt.close(fig)
    comparisons=[]
    for p in pairs:
        u=byid[p['id']]['metodos']['superior'];c=byid[p['id']]['metodos']['combinada']
        comparisons.append({'id':p['id'],'paciente':p['paciente'],'angulo_entre_solucoes_graus':geodesic_deg(np.array(u['R'])@np.array(c['R']).T),'rotacao_aplicada_superior_graus':geodesic_deg(np.array(u['R'])),'rotacao_aplicada_combinada_graus':geodesic_deg(np.array(c['R'])),'distancia_translacoes':float(np.linalg.norm(np.array(u['t'])-np.array(c['t']))),'RMSE_superior':u['RMSE'],'RMSE_combinada':c['RMSE']})
    save_csv('resultados/comparacao_metodos.csv',comparisons)
    print(json.dumps({'robustez':summary,'dispersao':ds},indent=2),flush=True)
if __name__=='__main__':main()
