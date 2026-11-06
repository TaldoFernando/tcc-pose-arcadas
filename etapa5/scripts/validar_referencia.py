from common import *

def main():
 old=csv_read('resultados/ensaios_original.csv');checks=[]
 for identifier in sorted({r['ID'] for r in old}):
  cloud=np.load(OUT/'clouds'/f'{identifier}.npz');cache=load(f'cache_pose/{identifier}/P016.json')
  for method in ['controle','anatomica']:
   R0=np.array(cache[method][0]['R'])
   for k,r in enumerate(cache[method][1:]):
    error=geodesic_deg(np.array(r['R'])@cloud[f'Q{k:02d}']@R0.T);reference=next(x for x in old if x['ID']==identifier and x['method']==method and int(x['trial'])==k+1)
    checks.append({'ID':identifier,'method':method,'trial':k+1,'absolute_error_delta_deg':abs(error-float(reference['error_deg'])),'RMSE_delta':abs(r['RMSE']-float(reference['RMSE']))})
 save('resultados/equivalencia_referencia_original.json',checks);assert max(r['absolute_error_delta_deg'] for r in checks)<1e-4
 print('REFERENCIA ORIGINAL REPRODUZIDA',len(checks),'ensaios')
if __name__=='__main__':main()
