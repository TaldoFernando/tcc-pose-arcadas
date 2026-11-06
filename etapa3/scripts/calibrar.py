from common import *
from sklearn.model_selection import GroupKFold,cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve,roc_auc_score
from scipy.special import expit
from datetime import datetime,timezone

def main():
    split=load_json('divisao.json');rules=load_json('regra.json');trials=[r for r in load_json('desenvolvimento/ensaios.json') if r['method']=='anatomica']
    assert len(trials)==400 and {r['id'] for r in trials}==set(split['desenvolvimento'])
    pairs={p['id']:p for p in load_json('pares.json')}
    X=np.array([[r['result']['icp_rmse'],r['result']['agreement_max_deg']] for r in trials]);y=np.array([r['failed'] for r in trials],int)
    groups=['|'.join([pairs[r['id']]['superior']['sha256'],pairs[r['id']]['inferior']['sha256']]) for r in trials]
    pipeline=make_pipeline(StandardScaler(),LogisticRegression(C=1,class_weight='balanced',solver='lbfgs',max_iter=1000,random_state=20261106))
    scores=cross_val_predict(pipeline,X,y,groups=groups,cv=GroupKFold(5),method='predict_proba')[:,1]
    fpr,tpr,thresholds=roc_curve(y,scores);valid=np.where((tpr>=.9)&np.isfinite(thresholds))[0]
    chosen=min(valid,key=lambda i:(fpr[i],-thresholds[i]));threshold=float(thresholds[chosen])
    pipeline.fit(X,y);scaler=pipeline[0];model=pipeline[1]
    gate={'features':['icp_rmse','agreement_max_deg'],'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'coefs':model.coef_[0].tolist(),'intercept':float(model.intercept_[0]),'threshold':threshold,'reject_if':'score >= threshold','score':'sigmoide de regressão logística padronizada, C=1, classes balanceadas; não probabilidade calibrada','cv':'GroupKFold 5 por conteúdo do par; limiar em predições OOF do desenvolvimento','OOF_AUC':float(roc_auc_score(y,scores)),'target_sensitivity':.9,'OOF_scores':scores.tolist(),'OOF_labels':y.tolist()}
    save_json('porta_qualidade.json',gate)
    paths=['regra.json','porta_qualidade.json','divisao.json','anatomical_pair.py','pca_pair.py','rigid_icp.py','scripts/replay.py','scripts/executar.py','scripts/common.py','scripts/desenvolver.py','scripts/calibrar.py','templates/superior.stl','templates/inferior.stl']
    save_json('congelamento.json',{'utc':datetime.now(timezone.utc).isoformat(),'hashes':{p:digest(OUT/p) for p in paths},'regra':'Nenhuma regra, template, peso, parâmetro ICP ou limiar pode ser alterado após avaliação de teste','test_evaluated':False})
    print('CONGELADO',rules,'GATE',threshold,'OOF AUC',gate['OOF_AUC'],flush=True)
if __name__=='__main__':main()
