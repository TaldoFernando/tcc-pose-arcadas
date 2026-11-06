"""Medidas repetidas: bootstrap de pacientes, nunca de ensaios isolados."""
from common import *
from anatomical_pair import anatomical_frame
from scipy.spatial.transform import Rotation
from collections import defaultdict,Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=10000;SEED_BOOT=20261107

def interval(values,draws):
    a=np.asarray(values,float);boots=a[draws].mean(axis=1);return {'estimate':float(a.mean()),'CI95':np.percentile(boots,[2.5,97.5]).tolist()}

def median_interval(values,draws):
    a=np.asarray(values,float);boots=np.median(a[draws],axis=1);return {'estimate':float(np.median(a)),'CI95':np.percentile(boots,[2.5,97.5]).tolist()}

def content_group(pair):return pair['superior']['sha256']+'|'+pair['inferior']['sha256']

def main():
    assert (OUT/'congelamento.json').exists()
    pairs={p['id']:p for p in load_json('pares.json')};split=load_json('divisao.json');selected=load_json('escolhas.json')['selected']
    template=np.load(OUT/'templates/P016.npz');F,_=anatomical_frame(template['upper'],template['lower'],1.,'pca_sign');save_json('resultados/frame_componentes.json',{'columns_LL_AP_vertical':F.tolist(),'template':'P016','decomposition':'SO(3) log (rotation vector), expressed in canonical frame; not sequential Euler angles'})
    summary={};patient_rows=[];component_rows=[];axis_summaries={};concentrations={};contrasts={};contrasts_rule={};CDFdata={}
    for subset,folder in [('dev','desenvolvimento'),('test','teste')]:
        own=load_json(folder+'/ensaios.json');old=load_json('referencias/'+folder+'/ensaios.json');oldbase={b['id']:b for b in load_json('referencias/'+folder+'/baselines.json')}
        records=[]
        for r in own:records.append({'id':r['id'],'method':r['method'],'trial':r['trial'],'error':r['error_deg'],'D':np.array(r['error_rotation'])})
        for r in old:
            R=np.array(r['result']['R']);Q=np.array(r['Q']);R0=np.array(oldbase[r['id']]['methods'][r['method']]['R']);records.append({'id':r['id'],'method':r['method'],'trial':r['trial'],'error':r['error_deg'],'D':R@Q@R0.T})
        ids=sorted({r['id'] for r in records});groups=defaultdict(list)
        for identifier in ids:groups[content_group(pairs[identifier])].append(identifier)
        cluster_ids=list(groups);rng=np.random.default_rng(SEED_BOOT+(0 if subset=='dev' else 1));draws_nom=rng.integers(0,len(ids),size=(B,len(ids)));draws_cluster=rng.integers(0,len(groups),size=(B,len(groups)))
        summary[subset]={};axis_summaries[subset]={};concentrations[subset]={};CDFdata[subset]={};matrices={}
        methods=sorted({r['method'] for r in records})
        for m in methods:
            matrix=np.array([[r['error'] for r in records if r['method']==m and r['id']==identifier] for identifier in ids]);assert matrix.shape==(len(ids),20)
            medians=np.median(matrix,axis=1);failures={t:np.mean(matrix>t,axis=1) for t in [2,3,5,10]}
            for i,identifier in enumerate(ids):patient_rows.append({'subset':subset,'id':identifier,'paciente':pairs[identifier]['paciente'],'method':m,'median_error_deg':medians[i],'mean_error_deg':matrix[i].mean(),'max_error_deg':matrix[i].max(),'failure_count5':int((matrix[i]>5).sum()),**{f'failure_pct_{t}deg':100*failures[t][i] for t in failures},'trials':20,'content_group':content_group(pairs[identifier])})
            vectors=[]
            for identifier in ids:
                local=[]
                for r in [r for r in records if r['method']==m and r['id']==identifier]:
                    v=np.rad2deg(Rotation.from_matrix(F.T@r['D']@F).as_rotvec());assert np.isclose(np.linalg.norm(v),r['error'],atol=1e-4)
                    component_rows.append({'subset':subset,'id':identifier,'method':m,'trial':r['trial'],'error_deg':r['error'],'lateral_deg':v[0],'AP_deg':v[1],'vertical_deg':v[2],'dominant_axis':['lateral','AP','vertical'][int(np.argmax(abs(v)))]});local.append(v)
                vectors.append(np.array(local))
            vectors=np.array(vectors);shares=np.mean(vectors**2/np.maximum(np.sum(vectors**2,axis=2,keepdims=True),1e-20),axis=1)
            patient_abs_median=np.median(np.abs(vectors),axis=1);dominant=Counter(['lateral','AP','vertical'][i] for i in np.argmax(patient_abs_median,axis=1))
            cshares=np.array([np.mean(shares[[ids.index(i) for i in groups[g]]],axis=0) for g in cluster_ids])
            axis_summaries[subset][m]={'mean_patient_abs_median_deg':dict(zip(['lateral','AP','vertical'],patient_abs_median.mean(0).tolist())),'patient_dominant_counts':dict(dominant),'content_balanced_energy_share':dict(zip(['lateral','AP','vertical'],cshares.mean(0).tolist()))}
            nom={'n':len(ids),'mean_patient_median':interval(medians,draws_nom),'median_patient_median':median_interval(medians,draws_nom),**{f'failure_rate_{t}deg':interval(failures[t],draws_nom) for t in failures}}
            cm=np.array([np.mean(medians[[ids.index(i) for i in groups[g]]]) for g in cluster_ids]);cf={t:np.array([np.mean(failures[t][[ids.index(i) for i in groups[g]]]) for g in cluster_ids]) for t in failures}
            conservative={'n':len(cluster_ids),'mean_patient_median':interval(cm,draws_cluster),'median_patient_median':median_interval(cm,draws_cluster),**{f'failure_rate_{t}deg':interval(cf[t],draws_cluster) for t in failures}}
            summary[subset][m]={'nominal_IDs':nom,'content_cluster_bootstrap':conservative,'median_of_patient_medians':float(np.median(medians)),'all_trials_mean_descriptive':float(matrix.mean()),'all_trials_max_descriptive':float(matrix.max())}
            counts=(matrix>5).sum(1);order=np.argsort(-counts,kind='stable');total=int(counts.sum());cum=np.cumsum(counts[order]);concentrations[subset][m]={'failures':total,'patients_any_failure':int((counts>0).sum()),'patients_half_failures_or_more':int((counts>=10).sum()),'patients_for50pct':int(np.searchsorted(cum,.5*total)+1) if total else 0,'patients_for80pct':int(np.searchsorted(cum,.8*total)+1) if total else 0,'top5_failure_share':float(counts[order[:5]].sum()/total) if total else 0,'top10_failure_share':float(counts[order[:10]].sum()/total) if total else 0,'ranking':[{'id':ids[i],'failures':int(counts[i]),'rate':float(counts[i]/20)} for i in order]}
            grid=np.unique(np.concatenate([np.linspace(0,15,151),np.linspace(15,180,166)]));pcdf=np.array([np.mean(row[:,None]<=grid,axis=0) for row in matrix]);ccdf=np.array([np.mean(pcdf[[ids.index(i) for i in groups[g]]],axis=0) for g in cluster_ids]);weights=np.zeros((2000,len(cluster_ids)))
            # Mesmas reamostragens por método => bandas pareadas no eixo paciente.
            for b in range(2000):weights[b]=np.bincount(draws_cluster[b],minlength=len(cluster_ids))/len(cluster_ids)
            boots=weights@ccdf;CDFdata[subset][m]={'x':grid.tolist(),'cdf_patient_content_mean':ccdf.mean(0).tolist(),'CI95_low':np.percentile(boots,2.5,axis=0).tolist(),'CI95_high':np.percentile(boots,97.5,axis=0).tolist()}
            matrices[m]=(cm,cf)
        contrasts[subset]={};contrasts_rule[subset]={}
        for m in methods:
            if m=='pca_controle':continue
            cm,cf=matrices[m];controlm,controlf=matrices['pca_controle']
            contrasts[subset][m]={'delta_mean_patient_median':interval(cm-controlm,draws_cluster),'delta_failure_rate5':interval(cf[5]-controlf[5],draws_cluster),'reference':'pca_controle','paired_patient_content_bootstrap':True}
        for m in methods:
            if m in ['anatomica','pca_controle']:continue
            cm,cf=matrices[m];basem,basef=matrices['anatomica']
            contrasts_rule[subset][m]={'delta_mean_patient_median':interval(cm-basem,draws_cluster),'delta_failure_rate5':interval(cf[5]-basef[5],draws_cluster),'reference':'anatomica','paired_patient_content_bootstrap':True}
        fig,axs=plt.subplots(1,2,figsize=(12,4.5))
        for m in ['pca_controle','anatomica']+selected:
            if m not in CDFdata[subset]:continue
            d=CDFdata[subset][m]
            for ax in axs:ax.plot(d['x'],d['cdf_patient_content_mean'],label=m)
        axs[0].set_xlim(0,15);axs[1].set_xlim(0,180)
        for ax in axs:
            for t in [2,3,5,10]:ax.axvline(t,color='gray',lw=.5,alpha=.5)
            ax.set(xlabel='Erro angular (°)',ylabel='Fração acumulada, pacientes com pesos iguais',ylim=(0,1.01));ax.grid(alpha=.2)
        axs[1].legend(fontsize=8);fig.suptitle('CDF — '+subset+' (bootstrap e bandas em JSON; conteúdos agrupados)');fig.tight_layout();fig.savefig(OUT/'resultados'/f'CDF_{subset}.png',dpi=160);plt.close(fig)
    for subset in ['dev','test']:
        display=['pca_controle','anatomica']+selected
        fig,ax=plt.subplots(figsize=(9,4.5));left=np.zeros(len(display))
        for axis,color in [('lateral','#477fa6'),('AP','#e6a04b'),('vertical','#64a486')]:
            values=np.array([100*axis_summaries[subset][m]['content_balanced_energy_share'][axis] for m in display]);ax.barh(display,values,left=left,label=axis,color=color);left+=values
        ax.set(xlabel='Fração de energia angular (%), peso igual por conteúdo-paciente',xlim=(0,100),title='Componentes SO(3) — '+subset);ax.legend();fig.tight_layout();fig.savefig(OUT/'resultados'/f'eixos_{subset}.png',dpi=160);plt.close(fig)
        fig,axs=plt.subplots(1,2,figsize=(12,4.5))
        for j,(key,scale,label) in enumerate([('mean_patient_median',1,'Média das medianas individuais (°)'),('failure_rate_5deg',100,'Taxa média de falha >5° (%)')]):
            for i,m in enumerate(display):
                d=summary[subset][m]['content_cluster_bootstrap'][key];x=scale*d['estimate'];lo,hi=np.array(d['CI95'])*scale;axs[j].errorbar(x,i,xerr=np.array([[x-lo],[hi-x]]),fmt='o',capsize=3,color='#376e94')
            axs[j].set_yticks(range(len(display)),display);axs[j].set_xlabel(label);axs[j].grid(axis='x',alpha=.2)
        fig.suptitle('Bootstrap de pacientes-conteúdo, IC95 — '+subset);fig.tight_layout();fig.savefig(OUT/'resultados'/f'IC_pacientes_{subset}.png',dpi=160);plt.close(fig)
    save_csv('resultados/por_paciente.csv',patient_rows);save_csv('resultados/componentes_rotacao.csv',component_rows);save_json('resultados/bootstrap_resumo.json',summary);save_json('resultados/bootstrap_contrastes.json',contrasts);save_json('resultados/bootstrap_contrastes_regra.json',contrasts_rule);save_json('resultados/concentracao_falhas.json',concentrations);save_json('resultados/eixos_resumo.json',axis_summaries);save_json('resultados/CDF.json',CDFdata)
    oracle=list(csv.DictReader((OUT/'resultados/oraculos292_componentes.csv').open()));by_patient=defaultdict(list)
    for r in oracle:
        v=np.array([float(r[k]) for k in ['lateral_deg','AP_deg','vertical_deg']]);by_patient[r['id']].append(v)
    shares=[]
    for values in by_patient.values():
        v=np.array(values);shares.append(np.mean(v*v/np.sum(v*v,axis=1)[:,None],axis=0))
    alias_groups=defaultdict(list)
    for identifier,values in by_patient.items():
        v=np.array(values);alias_groups[content_group(pairs[identifier])].append(np.mean(v*v/np.sum(v*v,axis=1)[:,None],axis=0))
    unique_shares=np.array([np.mean(values,axis=0) for values in alias_groups.values()])
    save_json('resultados/oraculos292_resumo.json',{'n_unique_contents':len(alias_groups),'content_balanced_energy_share':dict(zip(['lateral','AP','vertical'],unique_shares.mean(0).tolist())),'n_cases':len(oracle),'n_patient_ids':len(by_patient),'dominant_axis_case_counts':dict(Counter(r['dominant_axis'] for r in oracle)),'equal_patient_mean_energy_share':dict(zip(['lateral','AP','vertical'],np.mean(shares,axis=0).tolist())),'cases_per_patient':dict(Counter(r['id'] for r in oracle)),'condition':'somente os 292 casos cujo oráculo se afasta >5 graus; dois métodos antigos; medidas repetidas, não 292 pacientes'})
    print('ANALISE_CONCLUIDA: bootstrap B=10000 por paciente/cluster, componentes SO3, limiares, CDF, concentração.')
if __name__=='__main__':main()
