from analise_original import *
s=load('resultados/estratos_bootstrap.json');fig,ax=plt.subplots(figsize=(9,5));methods=['controle','anatomica','multi5_rmse']
for j,m in enumerate(methods):
 vals=[s[m][str(g)]['failure5'] for g in [1,2,3]];y=np.array([r['estimate']*100 for r in vals]);ci=np.array([r['CI95'] for r in vals])*100;x=np.arange(3)+(j-1)*.18
 ax.errorbar(x,y,yerr=np.vstack([y-ci[:,0],ci[:,1]-y]),fmt='o',capsize=4,label=m)
ax.set(xticks=np.arange(3),xticklabels=['Grupo 1 (21 conteúdos)','Grupo 2 (10 conteúdos)','Grupo 3 (16 conteúdos)'],ylabel='Falhas >5° por conteúdo-paciente (%)',ylim=(0,60),title='Teste original — média das taxas individuais e IC95% bootstrap');ax.legend();fig.tight_layout();fig.savefig(OUT/'resultados/estratos_falha5_IC95.png',dpi=160);plt.close(fig)
print('FIGURA ESTRATIFICADA CONCLUIDA')
