from common import *
from scipy.spatial.transform import Rotation
raw=np.load(OUT/'templates_raw/P016.npz');F,_=anatomical_frame(raw['upper'],raw['lower'],1.,'pca_sign')
bases={r['id']:r for r in json.loads((ROOT/'etapa3/teste/baselines.json').read_text())};rows=[]
for r in json.loads((ROOT/'etapa3/teste/ensaios.json').read_text()):
 method='controle' if r['method']=='pca_controle' else 'anatomica';D=np.array(r['result']['R'])@np.array(r['Q'])@np.array(bases[r['id']]['methods'][r['method']]['R']).T;v=np.rad2deg(Rotation.from_matrix(F.T@D@F).as_rotvec());result=r['result']
 rows.append({'ID':r['id'],'method':method,'trial':r['trial'],'error_deg':r['error_deg'],'vertical_deg':float(v[2]),'RMSE':result['RMSE'],'icp_rmse':result.get('icp_rmse',result.get('icp_inlier_rmse')),'template_ID':'P016','translation_error':r['translation_error']})
bank=[r['id'] for r in load('referencias/banco_original.json')]
for r in json.loads((ROOT/'etapa4/teste/ensaios.json').read_text()):
 if r['method']!='multi5_rmse':continue
 v=np.rad2deg(Rotation.from_matrix(F.T@np.array(r['error_rotation'])@F).as_rotvec());result=r['result']
 rows.append({'ID':r['id'],'method':'multi5_rmse','trial':r['trial'],'error_deg':r['error_deg'],'vertical_deg':float(v[2]),'RMSE':result['RMSE'],'icp_rmse':None,'template_ID':bank[result['selected_template_index']],'translation_error':None})
csv_save('resultados/ensaios_original.csv',rows);save('referencias/frame_original.json',{'columns_LL_AP_vertical':F.tolist(),'primary_ID':'P016'})
print('Referência extraída apenas com IDs:',len(rows))
