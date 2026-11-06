from analise_original import *

def main():
 rng=np.random.default_rng(SEED_STATS+2);cp=csv_read('resultados/por_conteudo_grupo.csv');out=[];quant=[]
 stats=load('resultados/estratos_bootstrap.json')
 for method,groups in stats.items():
  for group,metrics in groups.items():
   for metric,record in metrics.items():
    if not isinstance(record,dict):continue
    factor=100 if metric.startswith('failure') else 1
    out.append({'method':method,'grupo':group,'metric':metric,'estimate':record['estimate']*factor,'CI95_low':record['CI95'][0]*factor,'CI95_high':record['CI95'][1]*factor,'unit':'%' if factor==100 else ('graus' if metric=='median_error_deg' else 'mm_assumido'),'n_patient_contents':record['n_patient_contents'],'n_IDs':metrics['n_IDs']})
   x=np.array([float(r['median_error_deg']) for r in cp if r['method']==method and r['grupo']==group]);draw=rng.integers(0,len(x),size=(B,len(x)));ci=np.percentile(np.median(x[draw],axis=1),[2.5,97.5]);quant.append({'method':method,'grupo':group,'median_of_patient_medians_deg':float(np.median(x)),'CI95_low':ci[0],'CI95_high':ci[1],'n_patient_contents':len(x)})
 csv_save('resultados/estratos_IC95.csv',out);csv_save('resultados/mediana_das_medianas_grupo.csv',quant)
 # Falhas por paciente e grupos: CDF complementar dos quatro limiares.
 fig,ax=plt.subplots(figsize=(8,5))
 for method in ['controle','anatomica','multi5_rmse']:
  for group,style in zip([1,2,3],['-','--',':']):
   metrics=stats[method][str(group)];ax.plot([2,3,5,10],[100*metrics['failure'+str(t)]['estimate'] for t in [2,3,5,10]],style,marker='o',label=f'{method} G{group}')
 ax.set(xlabel='Limiar angular (graus)',ylabel='Falhas por conteúdo-paciente (%)',xticks=[2,3,5,10],ylim=(0,100));ax.legend(fontsize=8,ncol=3);fig.tight_layout();fig.savefig(OUT/'resultados/falhas_por_grupo.png',dpi=160);plt.close(fig)
 print('TABELAS COM IC95 E MEDIANAS POR GRUPO CONCLUIDAS')
if __name__=='__main__':main()
