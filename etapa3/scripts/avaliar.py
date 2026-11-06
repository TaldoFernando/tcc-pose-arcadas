from common import *
from scipy.special import expit
from sklearn.metrics import roc_auc_score,roc_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import Counter

def stats(v):
    v=np.array(v,float);q=np.percentile(v,[25,75]);return {'n':len(v),'media':float(v.mean()),'desvio_populacional':float(v.std()),'mediana':float(np.median(v)),'q1':float(q[0]),'q3':float(q[1]),'IQR':float(q[1]-q[0]),'max':float(v.max()),'menor5':int(np.sum(v<5)),'moderado_5a90':int(np.sum((v>=5)&(v<=90))),'inversoes_maior90':int(np.sum(v>90)),'falhas_maior5':int(np.sum(v>5)),'taxa_falha':float(np.mean(v>5))}

def gate_score(result,gate):
    X=np.array([result['icp_rmse'],result['agreement_max_deg']]);z=(X-np.array(gate['mean']))/np.array(gate['scale']);return float(expit(np.dot(z,gate['coefs'])+gate['intercept']))

def main():
    split=load_json('divisao.json');gate=load_json('porta_qualidade.json');old=list(csv.DictReader((OUT/'referencia_etapa2/ensaios.csv').open()));summary={};rejects=[];rocinfo={}
    for subset,folder in [('dev','desenvolvimento'),('test','teste')]:
        ids=split['desenvolvimento' if subset=='dev' else 'teste'];trials=load_json(folder+'/ensaios.json');summary[subset]={}
        methods={m:[r['error_deg'] for r in trials if r['method']==m] for m in ['anatomica','pca_controle']}
        for method in ['superior','combinada']:methods['etapa2_'+method]=[float(r['erro_angular_graus']) for r in old if r['id'] in ids and r['metodo']==method]
        for method,errors in methods.items():
            summary[subset][method]=stats(errors)
            fig,ax=plt.subplots(figsize=(8,4));v=np.maximum(np.array(errors),1e-4);bins=np.geomspace(1e-4,180.01,75)
            for mask,label,color in [(v<5,'Pequenos <5°','#3c9476'),((v>=5)&(v<=90),'Moderados 5–90°','#e5a13c'),(v>90,'Inversões >90°','#bf493b')]:ax.hist(v[mask],bins=bins,color=color,label=f'{label}: {int(mask.sum())}',alpha=.8)
            ax.set_xscale('log');ax.set(xlabel='Erro angular (°), escala log; zeros truncados em 1e-4',ylabel='Ensaios',title=f'{subset} — {method}');ax.axvline(5,color='black',lw=.8);ax.axvline(90,color='black',lw=.8);ax.legend();fig.tight_layout();fig.savefig(OUT/'resultados'/f'hist_log_{subset}_{method}.png',dpi=150);plt.close(fig)
        a=[r for r in trials if r['method']=='anatomica'];y=np.array([r['failed'] for r in a],int)
        scores=np.array(gate['OOF_scores']) if subset=='dev' else np.array([gate_score(r['result'],gate) for r in a])
        # OOF no desenvolvimento; teste é previsão do modelo congelado.
        signals={'ICP_RMSE':[r['result']['icp_rmse'] for r in a],'RMSE_simetrico':[r['result']['RMSE'] for r in a],'discordancia_candidatos':[r['result']['agreement_max_deg'] for r in a],'porta_combinada':scores}
        rocinfo[subset]={};fig,ax=plt.subplots(figsize=(6,5))
        for name,s in signals.items():
            auc=float(roc_auc_score(y,s));fpr,tpr,thresholds=roc_curve(y,s);rocinfo[subset][name]={'AUC':auc,'fpr':fpr.tolist(),'tpr':tpr.tolist()};ax.plot(fpr,tpr,label=f'{name}: AUC={auc:.3f}')
        ax.plot([0,1],[0,1],ls='--',color='gray');ax.set(xlabel='Falsos positivos: sucessos rejeitados',ylabel='Sensibilidade: falhas rejeitadas',title=f'Porta de qualidade — {subset}');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(OUT/'resultados'/f'ROC_{subset}.png',dpi=150);plt.close(fig)
        rejected=scores>=gate['threshold'];summary[subset]['porta']={'n':len(y),'threshold':gate['threshold'],'rejeitados':int(rejected.sum()),'falhas_rejeitadas':int(np.sum(rejected&(y==1))),'sucessos_rejeitados':int(np.sum(rejected&(y==0))),'falhas_escaparam':int(np.sum(~rejected&(y==1))),'aceitos':int((~rejected).sum()),'taxa_falha_entre_aceitos':float(np.mean(y[~rejected])) if (~rejected).any() else None,'pares_com_alguma_rejeicao':len({r['id'] for r,flag in zip(a,rejected) if flag})}
        for r,s,flag in zip(a,scores,rejected):rejects.append({'id':r['id'],'subset':subset,'ensaio':r['trial'],'erro':r['error_deg'],'falha':r['failed'],'score':s,'revisar_manualmente':bool(flag),'ICP_RMSE':r['result']['icp_rmse'],'RMSE_simetrico':r['result']['RMSE'],'discordancia_candidatos':r['result']['agreement_max_deg']})
    save_json('resultados/resumo.json',summary);save_json('resultados/ROC_AUC.json',rocinfo);save_csv('resultados/porta_decisoes.csv',rejects)
    diagnoses=list(csv.DictReader((OUT/'resultados/diagnostico_falhas_etapa2.csv').open()))
    causes={s:{m:dict(Counter(r['classificacao_operacional'] for r in diagnoses if r['subset']==s and r['metodo']==m)) for m in ['superior','combinada']} for s in ['dev','test']}
    save_json('resultados/causas_etapa2.json',causes)
    # Porta no baseline: triagem de 49 arquivos/par, sem verdade anatômica para ROC.
    baseline_reviews=[]
    for subset,folder in [('dev','desenvolvimento'),('test','teste')]:
        for r in load_json(folder+'/baselines.json'):
            result=r['methods']['anatomica'];score=gate_score(result,gate);baseline_reviews.append({'id':r['id'],'subset':subset,'score':score,'revisar_manualmente':score>=gate['threshold'],'nota':'não há rótulo anatômico do baseline; não calcular falhas escapadas aqui'})
    save_csv('resultados/porta_baselines.csv',baseline_reviews)
    print(json.dumps({'metricas':summary,'AUC':{s:{m:v['AUC'] for m,v in rocinfo[s].items()} for s in rocinfo},'causas':causes},indent=2),flush=True)
if __name__=='__main__':main()
