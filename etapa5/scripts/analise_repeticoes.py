from analise_original import *

def main():
 labels={r['ID']:{k:int(r[k]) if r[k] else None for k in ['grupo','goslon']} for r in csv_read('rotulos_local.csv')};pairs={p['id']:p for p in load('pares_ids.json')};plans=load('planos/divisoes.json');rng=np.random.default_rng(SEED_STATS+1)
 original=content_patients(patients(csv_read('resultados/ensaios_original.csv'),labels),pairs)
 allpatients=[];summary=[];diffs=[];balanced={}
 for plan in plans:
  rows=csv_read('resultados/ensaios_'+plan['name']+'.csv');prs=patients(rows,labels);cp=content_patients(prs,pairs)
  allpatients.extend([{**r,'split':plan['name']} for r in prs])
  for method in ['controle','anatomica','multi5_rmse']:
   data=[r for r in cp if r['method']==method];summary.append({'split':plan['name'],'method':method,'n_contents':len(data),**{k:float(np.mean([r[k] for r in data])) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']}})
  for a,b in [('anatomica','controle'),('multi5_rmse','controle'),('multi5_rmse','anatomica')]:
   aa={r['IDs']:r for r in cp if r['method']==a};bb={r['IDs']:r for r in cp if r['method']==b}
   for metric in ['median_error_deg','failure2','failure3','failure5','failure10']:
    values=[aa[i][metric]-bb[i][metric] for i in aa];diffs.append({'split':plan['name'],'comparison':a+' menos '+b,'metric':metric,**ci_mean(values,rng)})
  if plan['name']=='balanceado_original':
   for group in [1,2,3]:
    data=[r for r in cp if r['method']=='multi5_rmse' and r['grupo']==group];old={r['IDs']:r for r in original if r['method']=='multi5_rmse' and r['grupo']==group}
    balanced[str(group)]={k:ci_mean([r[k] for r in data],rng) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']}
    balanced[str(group)]['paired_delta_failure5']=ci_mean([r['failure5']-old[r['IDs']]['failure5'] for r in data],rng)
   data=[r for r in cp if r['method']=='multi5_rmse'];old={r['IDs']:r for r in original if r['method']=='multi5_rmse'}
   balanced['overall']={k:ci_mean([r[k] for r in data],rng) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']};balanced['overall']['paired_delta_failure5']=ci_mean([r['failure5']-old[r['IDs']]['failure5'] for r in data],rng)
   # Conteúdo com rótulo ordinal conflitante é excluído da tendência, como no protocolo.
   valid=[r for r in data if r['goslon'] is not None];balanced['correlations']={'goslon_failure5':corr([r['goslon'] for r in valid],[r['failure5'] for r in valid],rng),'RMSE_failure5':corr([r['median_RMSE'] for r in data],[r['failure5'] for r in data],rng)}
   csv_save('resultados/balanceado_por_ID.csv',prs)
   choices=[]
   for group in [1,2,3]:
    clusters=defaultdict(list)
    for r in data:
     if r['grupo']==group:clusters[r['IDs']]=r['IDs'].split(',')
    for tid in plan['bank']:
     proportions=[np.mean([np.mean([r['template_ID']==tid for r in rows if r['method']=='multi5_rmse' and r['ID']==i]) for i in ids]) for ids in clusters.values()]
     choices.append({'query_grupo':group,'template_ID':tid,'template_grupo':labels[tid]['grupo'],'mean_patient_content_fraction':float(np.mean(proportions))})
   csv_save('resultados/templates_balanceados_por_grupo.csv',choices)
 # Original summary CI, preserving content weighting.
 original_ci={}
 for method in ['controle','anatomica','multi5_rmse']:
  d=[r for r in original if r['method']==method];original_ci[method]={k:ci_mean([r[k] for r in d],rng) for k in ['median_error_deg','failure2','failure3','failure5','failure10','median_RMSE']}
 save('resultados/original_global_bootstrap.json',original_ci);save('resultados/balanceado_bootstrap.json',balanced);csv_save('resultados/repeticoes_por_ID.csv',allpatients);csv_save('resultados/repeticoes_resumo.csv',summary);save('resultados/diferencas_pareadas_por_divisao.json',diffs)
 distributions=[]
 for comparison in sorted({r['comparison'] for r in diffs}):
  for metric in ['median_error_deg','failure2','failure3','failure5','failure10']:
   vals=np.array([r['estimate'] for r in diffs if r['split'].startswith('seed_') and r['comparison']==comparison and r['metric']==metric]);q=np.percentile(vals,[25,50,75]);distributions.append({'comparison':comparison,'metric':metric,'n_splits':len(vals),'mean':float(vals.mean()),'q25':q[0],'median':q[1],'q75':q[2],'min':float(vals.min()),'max':float(vals.max()),'splits_improved':int(np.sum(vals<0))})
 csv_save('resultados/estabilidade_diferencas.csv',distributions)
 fig,axs=plt.subplots(1,2,figsize=(12,5))
 for ax,metric,mult,label in zip(axs,['failure5','median_error_deg'],[100,1],['Diferença na falha >5° (p.p.)','Diferença na média das medianas (graus)']):
  comparisons=sorted({r['comparison'] for r in diffs});vals=[[r['estimate']*mult for r in diffs if r['split'].startswith('seed_') and r['comparison']==c and r['metric']==metric] for c in comparisons]
  ax.boxplot(vals,showfliers=False,labels=[c.replace(' menos ','\nmenos ') for c in comparisons]);[ax.scatter(np.full(len(v),i+1),v,s=18) for i,v in enumerate(vals)];ax.axhline(0,c='gray',lw=.8);ax.set_ylabel(label);ax.tick_params(axis='x',labelsize=8)
 fig.suptitle('10 divisões sobrepostas: distribuição descritiva, sem independência entre divisões');fig.tight_layout();fig.savefig(OUT/'resultados/estabilidade.png',dpi=160);plt.close(fig)
 print('ANALISE BALANCEADA E 10 DIVISOES CONCLUIDA')
if __name__=='__main__':main()
