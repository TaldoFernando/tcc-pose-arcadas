"""Prepara cópias e desenho; não cria marcações anatômicas."""
from pathlib import Path
import sys,json,csv,hashlib,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'etapa8';SEED=20261108
sys.path.insert(0,str(ROOT/'etapa6'))
from render_views import read_stl
def save(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False))
def csvsave(name,rows):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stl_write(path,tri):
 path.parent.mkdir(parents=True,exist_ok=True);dt=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')]);a=np.zeros(len(tri),dt);a['vertices']=tri;n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-20);a['normal']=n
 with path.open('wb') as f:f.write(b'LOCAL_CANONICAL_CARTESIAN_NOT_ANATOMICAL_RAS'.ljust(80,b' '));f.write(len(tri).to_bytes(4,'little'));f.write(a.tobytes())
def matrix(R,t):
 T=np.eye(4);T[:3,:3]=R;T[:3,3]=t;return T
def main():
 if (OUT/'plano.json').exists():raise SystemExit('Desenho já existente; não sobrescrever seleção.')
 units=json.load(open(ROOT/'etapa7b/unidades.json'));split=json.load(open(ROOT/'etapa5/divisao_original.json'));rng=np.random.default_rng(SEED);bank=['P016','P004','P045','P029','P002'];study=[];pilot=[];repeat=[]
 for group in [1,2,3]:
  test=sorted(u['ID'] for u in units if u['grupo']==group and any(i in split['teste'] for i in u['aliases']));selected=sorted(rng.choice(test,8,replace=False).tolist());study+=selected;repeat+=sorted(rng.choice(selected,4 if group==1 else 3,replace=False).tolist())
  dev=sorted(u['ID'] for u in units if u['grupo']==group and not any(i in split['teste'] for i in u['aliases']) and u['ID'] not in bank);pilot.append(str(rng.choice(dev)))
 byid={u['ID']:u for u in units};study=sorted(study);pilot=sorted(pilot);repeat=sorted(repeat)
 lm=[]
 for arch,prefix,fdibase in [('superior','U',10),('inferior','L',40)]:
  for tooth,desc,purpose in [(1,'ponto médio mesiodistal da borda incisal visível, sobre a aresta e não na face vestibular','alinhamento e proxy de overjet'),(3,'ápice anatômico da cúspide visível do canino','alinhamento'),(6,'ápice da cúspide mesiovestibular do primeiro molar permanente','alinhamento')]:
   for side in ['R','L']:
    quadrant=(1 if side=='R' else 2) if arch=='superior' else (4 if side=='R' else 3);fdicode=quadrant*10+tooth
    lm.append({'label':f'{prefix}{tooth}_{side}','arcada':arch,'familia':purpose,'definicao_provisoria':f'Dente FDI {fdicode}: {desc}. R/L são lados clínicos do paciente, não lados da tela.','ausencia':'Se ausente, decíduo, desgastado sem ápice identificável, artefato ou lateralidade incerta: registrar motivo; não substituir por outro dente.','propagar':True,'validado':False})
 for level,desc in [('A','limite anterior visível da descontinuidade entre os segmentos alveolopalatinos'),('P','limite posterior visível da mesma descontinuidade')]:
  for segment in ['MAIOR','MENOR']:
   lm.append({'label':f'F_{level}_{segment}','arcada':'superior','familia':'fissura exploratória','definicao_provisoria':f'Na margem do segmento {segment.lower()}, no {desc}; os dois pontos do mesmo nível devem corresponder à mesma seção anatômica, a ser definida pela orientadora.','ausencia':'Somente hipótese de fissura unilateral aberta com dois segmentos identificáveis; caso operado/fechado, bilateral, limites incertos ou topologia diferente: não aplicável ou não visível; não inferir a fissura pelo grupo.','propagar':False,'validado':False})
 save('landmarks_propostos.json',{'version':'PROPOSTA_V1_NAO_VALIDADA','approved':False,'approved_by_role':None,'approved_date':None,'references_confirmed_for_dental_STL':False,'landmarks':lm})
 plan={'seed':SEED,'study_IDs':study,'pilot_development_IDs':pilot,'template_ID':'P016','repeat_IDs':repeat,'study_contents':24,'per_group':8,'repeat_per_group':{'1':4,'2':3,'3':3},'raters':['A1','A2'],'sessions':['T1','T2'],'minimum_repeat_days':14,'expected_study_sessions':68,'normalization_rules_may_be_changed':False,'study_source':'somente conteúdos únicos do teste original; sem conteúdo de grupo conflitante','annotation_mode':'assistida por propostas de template humano, sempre corrigidas/revisadas por pessoas','pilot_in_main_analysis':False,'template_in_main_analysis':False,'group_blinding':'grupos somente para coordenação; não mostrados pelo script Slicer','optional_detector':'NÃO IMPLEMENTADO NEM EXECUTADO; depende de análise humana concluída e protocolo separado'}
 save('plano.json',plan);csvsave('amostra_coordenacao.csv',[{'ID':i,'grupo':byid[i]['grupo'],'divisao_original':'teste','repetir_T2':i in repeat,'ID_conteudo':i,'aliases':';'.join(byid[i]['aliases'])} for i in study]);csvsave('piloto_coordenacao.csv',[{'ID':i,'grupo':byid[i]['grupo'],'divisao_original':'desenvolvimento','finalidade':'validar definições; excluir da análise principal'} for i in pilot])
 tasks=[]
 for rater in ['A1','A2']:
  for session,ids in [('T1',study),('T2',repeat)]:
   order=rng.permutation(ids).tolist()
   for k,i in enumerate(order):tasks.append({'ID':i,'avaliador':rater,'sessao':session,'ordem':k+1,'data_real':'','data_minima_T2':'','estado':'pendente','arquivo_json':f'{i}_{rater}_{session}.json','revisao':'pendente'})
 csvsave('acompanhamento.csv',tasks)
 for rater in ['A1','A2']:save(f'listas/{rater}.json',[{k:r[k] for k in ['ID','avaliador','sessao','ordem','arquivo_json']} for r in tasks if r['avaliador']==rater])
 transforms={};assets=[];pairs={r['id']:r for r in json.load(open(ROOT/'etapa5/pares_ids.json'))};canonical={r['ID']:r for r in json.load(open(ROOT/'etapa6/stl/transformacoes.json'))};selected=sorted(set(study+pilot+['P016']))
 for i in selected:
  z=np.load(ROOT/'etapa7b/features'/f'{i}.npz');baseline=json.loads(str(z['baseline_pose']));T={'nenhuma':np.eye(4)}
  for method in ['controle','anatomica']:T[method]=matrix(baseline[method]['R'],baseline[method]['t'])
  T['multi5_rmse']=matrix(canonical[i]['R'],canonical[i]['t']);cloud=np.load(ROOT/'etapa5/clouds'/f'{i}.npz');center=np.concatenate([cloud['superior_base'],cloud['inferior_base']]).mean(0)
  for m,M in T.items():assert np.linalg.det(M[:3,:3])>0 and np.allclose(M[:3,:3].T@M[:3,:3],np.eye(3),atol=1e-8)
  transforms[i]={'methods':{k:v.tolist() for k,v in T.items()},'raw_geometry_centroid':center.tolist(),'landmarks_used_for_transform':False,'source_frozen_features_sha256':sha(ROOT/'etapa7b/features'/f'{i}.npz')}
  M=T['multi5_rmse']
  for arch in ['superior','inferior']:
   source=ROOT/'etapa5'/pairs[i][arch]['arquivo'];assert sha(source)==pairs[i][arch]['sha256'];tri=read_stl(source);out=OUT/'assets'/i/f'{arch}.stl';stl_write(out,tri@M[:3,:3].T+M[:3,3]);assets.append({'ID':i,'arcada':arch,'arquivo':str(out.relative_to(OUT)),'sha256':sha(out),'original_copy_sha256':sha(source),'frame':'CANONICAL_STL_CARTESIAN','normalizacao':'multi5_rmse_congelada'})
  print('CÓPIA NORMALIZADA',i,flush=True)
 save('transformacoes_congeladas.json',{'frame':'CANONICAL_STL_CARTESIAN','points_convention':'colunas: p_metodo=R@p_original+t; marcação em multi5; p_original=R_multi.T@(p_marcado-t_multi)','IDs':transforms});csvsave('manifesto_assets.csv',assets)
 for folder in ['marcacoes','template','resultados','qa','tests','outputs/etapa8']: (OUT/folder).mkdir(parents=True,exist_ok=True)
 save('status.json',{'status':'AGUARDANDO_VALIDACAO_DEFINICOES_E_MARCACOES_HUMANAS','landmarks_humanos_criados':0,'analises_reais_executadas':False,'template_humano':'PENDENTE','detector_opcional':'NAO_INICIADO'})
 save('congelamento.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'selection_before_annotations':True,'files':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'plano.json',OUT/'transformacoes_congeladas.json',ROOT/'etapa5/anatomical_pair.py',ROOT/'etapa5/pca_pair.py',ROOT/'etapa5/rigid_icp.py',ROOT/'etapa6/stl/modelo_normalizacao.npz',ROOT/'etapa6/stl/transformacoes.json']},'provisional_definition_sha256':sha(OUT/'landmarks_propostos.json'),'definitions_must_be_validated_on_development_only':True,'test_landmarks_must_not_update_normalization':True})
 print('24 conteúdos, 10 remarcações, 68 sessões principais; 3 pilotos separados; template humano pendente.')
if __name__=='__main__':main()
