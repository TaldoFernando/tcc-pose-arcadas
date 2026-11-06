from common import *
from collections import defaultdict,Counter
pairs=load('pares_ids.json');byid={p['id']:p for p in pairs};labels={r['ID']:int(r['grupo']) for r in csv_read('rotulos_local.csv')};split0=load('divisao_original.json')
descriptors={}
for p in pairs:
 d=np.load(OUT/'clouds'/f'{p["id"]}.npz');u=d['superior_base'];l=d['inferior_base'];F,_=anatomical_frame(u,l,1.,'pca_sign');descriptors[p['id']]=np.concatenate([np.ptp((u-u.mean(0))@F,axis=0),np.ptp((l-l.mean(0))@F,axis=0)])
def unique_dev(ids):
 seen=set();out=[]
 for i in sorted(ids):
  h=key(byid[i])
  if h not in seen:seen.add(h);out.append(i)
 return out
def primary(ids):
 u=unique_dev(ids);D=np.zeros((len(u),len(u)))
 for i,j in itertools.combinations(range(len(u)),2):D[i,j]=D[j,i]=angular(np.array(byid[u[i]]['superior_axes']),np.array(byid[u[j]]['superior_axes']))
 return u[int(np.argmin(D.sum(1)))]
def bank(ids,p0,balance=False):
 u=unique_dev(ids);X=np.array([descriptors[i] for i in u]);X=(X-X.mean(0))/np.maximum(X.std(0),1e-8);selected=[u.index(p0)]
 quotas={}
 if balance:
  present=sorted(set(labels[i] for i in u));quotas={g:0 for g in present}
  for k in range(5):quotas[present[k%len(present)]]+=1
  # Primary counts against its own group; any unavailable slots redistributed deterministically.
 while len(selected)<5:
  candidates=[j for j in range(len(u)) if j not in selected]
  if balance:
   counts=Counter(labels[u[j]] for j in selected);eligible=[j for j in candidates if counts[labels[u[j]]]<quotas[labels[u[j]]]]
   if eligible:candidates=eligible
  distances=np.min(np.linalg.norm(X[:,None,:]-X[selected][None,:,:],axis=2),axis=1);j=max(candidates,key=lambda j:(distances[j],-j));selected.append(j)
 return [u[j] for j in selected],quotas
plans=[]
# Original held-out comparison: balanced bank, all other inference rules unchanged.
b0,quota=bank(split0['desenvolvimento'],'P016',True)
plans.append({'name':'balanceado_original','seed':split0['seed'],'dev':split0['desenvolvimento'],'test':split0['teste'],'primary':'P016','bank':b0,'balanced':True,'quotas':quota})
for seed in range(20261110,20261120):
 groups=defaultdict(list)
 for p in pairs:groups[key(p)].append(p['id'])
 g=list(groups.values());rng=np.random.default_rng(seed);rng.shuffle(g);dp={0:[]}
 for ids in g:
  for n,chosen in list(dp.items())[::-1]:
   new=n+len(ids)
   if new<=20 and new not in dp:dp[new]=chosen+ids
 dev=sorted(dp[20]);test=sorted(i for i in byid if i not in dev);p0=primary(dev);b,_=bank(dev,p0,False)
 plans.append({'name':f'seed_{seed}','seed':seed,'dev':dev,'test':test,'primary':p0,'bank':b,'balanced':False})
save('planos/divisoes.json',plans)
# Pré-registro de hipóteses e análises; rótulos não são argumentos do normalizador.
save('protocolo.json',{'B_bootstrap':10000,'B_permutation':10000,'seed_stats':20261120,'methods':['controle','anatomica','multi5_rmse'],'original_split':'20/49 unchanged','stability_splits':10,'trials_per_ID':20,'group_label':'grupo do diretório; GOSLON extraído literalmente, não validado','group_goslon_audit':{'1':[1,2],'2':[3],'3':[4,5]},'inference_inputs':'clouds and template geometry only; no labels','balanced_bank':'5 templates; quotas as equal as possible, extras ascending group; P016 fixed primary; geometry farthest-first restricted to dev','stability_bank':'new dev PCA medoid primary; 5 geometric farthest-first templates; no query labels','label_conflicts':'exclude content groups with inconsistent GOSLON from primary GOSLON trend; exclude cross-group content conflicts from group-stratified summaries; never correct labels','trend':'Spearman on patient-content failure rates; permutation p two-sided; bootstrap CI over patient-content','RMSE_failure':'Spearman of per-patient median chosen symmetric RMSE and failure rate >5; association not explanation/causality','vertical_bias':'signed SO3 vertical components; per-patient mean and population SD; bias fraction mu²/(mu²+sigma²), equal patient-content weights; near-pi sign ambiguity noted','split_differences':'descriptive distribution, not 10 independent trials; paired mean failure5 and mean patient medians by content cluster','classifier':'prepare stub only, never execute'})
print('PLANOS',[(p['name'],p['primary'],p['bank']) for p in plans],flush=True)
