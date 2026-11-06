from common import *
from anatomical_pair import run_icp
from scipy.spatial.transform import Rotation

def direct(u,l,tu,tl):
 Fs,_=anatomical_frame(u,l,1.,'pca_sign');Ft,_=anatomical_frame(tu,tl,1.,'pca_sign');source=np.concatenate([u[::2],l[::2]]);target=np.concatenate([tu[::2],tl[::2]]);cs=source.mean(0);ct=target.mean(0);out=[]
 for J in [np.eye(3),Rotation.from_rotvec([0,0,np.deg2rad(10)]).as_matrix(),Rotation.from_rotvec([0,0,np.deg2rad(-10)]).as_matrix(),Rotation.from_rotvec([np.deg2rad(10),0,0]).as_matrix()]:
  R=Ft@J@Fs.T;T=np.eye(4);T[:3,:3]=R;T[:3,3]=ct-R@cs;out.append(run_icp(source,target,T))
 return min(out,key=lambda r:r['RMSE'])

def main():
 plans=load('planos/divisoes.json');checks=[]
 for plan in plans[:3]:
  identifier=next(i for i in plan['test'] if all((OUT/'cache_pose'/i/f'{t}.json').exists() for t in plan['bank']));cloud=np.load(OUT/'clouds'/f'{identifier}.npz')
  for tid in plan['bank'][1:3]:
   raw=np.load(OUT/'templates_raw'/f'{tid}.npz');a=plan['alignments'][tid];C=np.array(a['R']);ct=np.array(a['t']);tu=(raw['upper']-raw['origin'])@C.T+ct;tl=(raw['lower']-raw['origin'])@C.T+ct
   for index in [0,1]:
    u=cloud['superior_base'] if index==0 else cloud['superior00'];l=cloud['inferior_base'] if index==0 else cloud['inferior00'];r=direct(u,l,tu,tl);cached=load(f'cache_pose/{identifier}/{tid}.json')['anatomica'][index];R=C@np.array(cached['R']);t=C@np.array(cached['t'])+ct
    checks.append({'split':plan['name'],'ID':identifier,'template_ID':tid,'trial':index,'rotation_delta_deg':geodesic_deg(R@np.array(r['R']).T),'translation_delta':float(np.linalg.norm(t-r['t'])),'RMSE_delta':abs(r['RMSE']-cached['RMSE'])})
 save('resultados/equivalencia_cache.json',checks);assert max(r['rotation_delta_deg'] for r in checks)<.001 and max(r['RMSE_delta'] for r in checks)<1e-6
 print('CACHE E AJUSTE DIRETO EQUIVALENTES',len(checks),'comparações')
if __name__=='__main__':main()
