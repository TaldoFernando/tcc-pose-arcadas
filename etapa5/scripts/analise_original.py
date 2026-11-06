from common import *
from collections import defaultdict,Counter
from scipy.stats import rankdata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SEED_STATS=20261120;B=10000

def ci_mean(x,rng):
 x=np.asarray(x,float);draw=rng.integers(0,len(x),size=(B,len(x)));return {'estimate':float(x.mean()),'CI95':np.percentile(x[draw].mean(1),[2.5,97.5]).tolist(),'n_patient_contents':len(x)}

def corr(x,y,rng):
 x=np.asarray(x,float);y=np.asarray(y,float);n=len(x)
 if n<4 or np.std(x)==0 or np.std(y)==0:return {'n':n,'rho':None,'reason':'amostra pequena ou variável constante'}
 rx=rankdata(x);ry=rankdata(y);cx=rx-rx.mean();cy=ry-ry.mean();rho=float(cx@cy/np.sqrt((cx@cx)*(cy@cy)))
 shuffled=np.array([rng.permutation(cx) for _ in range(B)]);permuted=shuffled@cy/np.sqrt((cx@cx)*(cy@cy));p=float((1+np.sum(abs(permuted)>=abs(rho)))/(B+1))
 draw=rng.integers(0,n,size=(B,n));bx=rankdata(x[draw],axis=1);by=rankdata(y[draw],axis=1);bx-=bx.mean(1,keepdims=True);by-=by.mean(1,keepdims=True);den=np.sqrt(np.sum(bx*bx,axis=1)*np.sum(by*by,axis=1));valid=den>0;boot=np.sum(bx[valid]*by[valid],axis=1)/den[valid]
 return {'n':n,'rho':rho,'CI95':np.percentile(boot,[2.5,97.5]).tolist(),'permutation_p_two_sided':p,'bootstrap_valid':int(valid.sum()),'B':B,'unit':'patient-content, not trial'}

def patients(rows,labels):
 out=[]
 for method in sorted({r['method'] for r in rows}):
  for identifier in sorted({r['ID'] for r in rows if r['method']==method}):
   a=[r for r in rows if r['ID']==identifier and r['method']==method];error=np.array([float(r['error_deg']) for r in a]);z=np.array([float(r['vertical_deg']) for r in a]);rmse=np.array([float(r['RMSE']) for r in a]);mu=z.mean();var=z.var()
   out.append({'ID':identifier,'method':method,'grupo':labels[identifier]['grupo'],'goslon':labels[identifier]['goslon'],'median_error_deg':float(np.median(error)),**{f'failure{t}':float(np.mean(error>t)) for t in [2,3,5,10]},'median_RMSE':float(np.median(rmse)),'vertical_signed_mean':float(mu),'vertical_SD_population':float(np.sqrt(var)),'vertical_bias_energy':float(mu*mu),'vertical_noise_energy':float(var),'vertical_bias_fraction':float(mu*mu/(mu*mu+var)) if mu*mu+var else 0,'inversions90':int(np.sum(error>90)),'n_trials':len(a)})
 return out

def content_patients(prs,pairs):
 clusters=defaultdict(list)
 for r in prs:clusters[(r['method'],key(pairs[r['ID']]))].append(r)
 out=[]
 for (method,h),rs in clusters.items():
  groups={r['grupo'] for r in rs};goslon={r['goslon'] for r in rs};mus=np.array([r['vertical_signed_mean'] for r in rs]);second=np.array([r['vertical_noise_energy']+r['vertical_bias_energy'] for r in rs]);mu=mus.mean();noise=float(second.mean()-mu*mu)
  out.append({'IDs':','.join(r['ID'] for r in rs),'method':method,'grupo':next(iter(groups)) if len(groups)==1 else None,'goslon':next(iter(goslon)) if len(goslon)==1 else None,'group_conflict':len(groups)>1,'goslon_conflict':len(goslon)>1,**{k:float(np.mean([r[k] for r in rs])) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']},'vertical_signed_mean':float(mu),'vertical_variance':noise,'vertical_bias_energy':float(mu*mu),'vertical_noise_energy':noise,'aliases':len(rs)})
 return out

def main():
 labels={r['ID']:{'grupo':int(r['grupo']) if r['grupo'] else None,'goslon':int(r['goslon']) if r['goslon'] else None} for r in csv_read('rotulos_local.csv')};pairs={p['id']:p for p in load('pares_ids.json')};rows=csv_read('resultados/ensaios_original.csv');prs=patients(rows,labels);cp=content_patients(prs,pairs);csv_save('resultados/por_ID_grupo.csv',prs);csv_save('resultados/por_conteudo_grupo.csv',cp)
 rng=np.random.default_rng(SEED_STATS);summaries={};correlations={};vertical=[];group_rows=[];choices=[]
 flagged={r['ID'] for r in csv_read('inconsistencias_rotulos.csv') if r['ID']}
 for method in ['controle','anatomica','multi5_rmse']:
  contents=[r for r in cp if r['method']==method];summaries[method]={}
  for group in [1,2,3]:
   data=[r for r in contents if r['grupo']==group and not r['group_conflict']]
   summary={k:ci_mean([r[k] for r in data],rng) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']};summary['n_IDs']=sum(r['aliases'] for r in data);summaries[method][str(group)]=summary
   group_rows.append({'method':method,'grupo':group,'n_contents':len(data),'n_IDs':summary['n_IDs'],**{k:summary[k]['estimate'] for k in summary if isinstance(summary[k],dict)}})
   mu=np.array([r['vertical_signed_mean'] for r in data]);noise=np.array([r['vertical_noise_energy'] for r in data]);bias=np.mean(mu*mu);spread=noise.mean();vertical.append({'method':method,'grupo':group,'n_contents':len(data),'signed_group_mean':float(mu.mean()),'SD_between_patient_means':float(mu.std()),'mean_within_patient_SD':float(np.mean(np.sqrt(noise))),'mixture_SD':float(np.sqrt(noise.mean()+mu.var())),'bias_energy':float(bias),'noise_energy':float(spread),'bias_fraction':float(bias/(bias+spread)),'predominante':'vies' if bias>spread else 'espalhamento'})
  valid=[r for r in contents if r['goslon'] is not None and not r['goslon_conflict']]
  sensitivity=[r for r in valid if not (set(r['IDs'].split(','))&flagged)]
  correlations[method]={'goslon_failure5':corr([r['goslon'] for r in valid],[r['failure5'] for r in valid],rng),'goslon_failure5_without_flagged_labels':corr([r['goslon'] for r in sensitivity],[r['failure5'] for r in sensitivity],rng),'RMSE_failure5':corr([r['median_RMSE'] for r in contents],[r['failure5'] for r in contents],rng),'excluded_GOSLON_conflict_IDs':[r['IDs'] for r in contents if r['goslon_conflict']]}
  for group in [1,2,3]:
   data=[r for r in contents if r['grupo']==group];correlations[method][f'RMSE_failure5_group{group}']=corr([r['median_RMSE'] for r in data],[r['failure5'] for r in data],rng)
 # Frequência de templates: contagens brutas e proporção média por paciente-conteúdo.
 bank=[r['id'] for r in load('referencias/banco_original.json')]
 multi=[r for r in rows if r['method']=='multi5_rmse']
 for group in [1,2,3]:
  groupids={r['ID'] for r in prs if r['method']=='multi5_rmse' and r['grupo']==group};content_ids=defaultdict(list)
  for identifier in groupids:content_ids[key(pairs[identifier])].append(identifier)
  for tid in bank:
   raw_count=sum(r['ID'] in groupids and r['template_ID']==tid for r in multi)
   proportions=[]
   for identifiers in content_ids.values():proportions.append(np.mean([np.mean([r['template_ID']==tid for r in multi if r['ID']==i]) for i in identifiers]))
   choices.append({'query_grupo':group,'template_ID':tid,'template_grupo':labels[tid]['grupo'],'trial_count':raw_count,'mean_patient_content_fraction':float(np.mean(proportions)),'n_patient_contents':len(proportions)})
 csv_save('resultados/templates_por_grupo.csv',choices);save('resultados/estratos_bootstrap.json',summaries);csv_save('resultados/estratos_resumo.csv',group_rows);save('resultados/correlacoes.json',correlations);csv_save('resultados/vertical_por_grupo.csv',vertical)
 # Vertical patient plots, signed means retain individual IDs only.
 fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True)
 for ax,method in zip(axs,['controle','anatomica','multi5_rmse']):
  data=sorted([r for r in prs if r['method']==method],key=lambda r:r['ID']);x=np.arange(len(data));mu=np.array([r['vertical_signed_mean'] for r in data]);sd=np.array([r['vertical_SD_population'] for r in data]);ax.errorbar(x,mu,yerr=sd,fmt='.',capsize=2);ax.axhline(0,color='gray',lw=.7);ax.set(ylabel='Vertical (graus)',title=method+' — média assinada ± desvio entre 20 ensaios');ax.set_xticks(x,[r['ID'] for r in data],rotation=90,fontsize=7)
 fig.tight_layout();fig.savefig(OUT/'resultados/vertical_por_ID.png',dpi=160);plt.close(fig)
 print('ANALISE ORIGINAL CONCLUIDA: IDs, grupos, bootstrap, Spearman, templates e vertical; sem regra ajustada.')
if __name__=='__main__':main()
