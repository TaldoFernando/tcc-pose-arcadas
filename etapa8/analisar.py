"""Análise somente após marcações humanas; propostas/template/piloto são excluídos."""
from pathlib import Path
import argparse,csv,datetime,json,collections
import numpy as np
from e8_common import ROOT,load,sha,protocol,protocol_path,verify_frozen,validate_annotation,convert_point,save_csv,PRESENT
SEED=20261108;B=10000
def icc_absolute(y):
 """ICC(A,1), ANOVA bidirecional, concordância absoluta, medida única.

 Inter: avaliadores aleatórios. Intra: sessões fixas/misto. Mesma equação;
 não confundir com ICC(3,1) de consistência. Suporta dimensões bootstrap.
 """
 y=np.asarray(y,float)
 if y.ndim<2:raise ValueError('ICC requer conteúdos por observações.')
 n,k=y.shape[-2:]
 if n<2 or k<2:return np.full(y.shape[:-2],np.nan)
 grand=y.mean(axis=(-2,-1),keepdims=True);rows=y.mean(-1,keepdims=True);cols=y.mean(-2,keepdims=True)
 msr=k*np.sum((rows-grand)**2,axis=(-2,-1))/(n-1);msc=n*np.sum((cols-grand)**2,axis=(-2,-1))/(k-1);mse=np.sum((y-rows-cols+grand)**2,axis=(-2,-1))/((n-1)*(k-1));den=msr+(k-1)*mse+k*(msc-mse)/n
 return np.divide(msr-mse,den,out=np.full_like(den,np.nan,dtype=float),where=np.abs(den)>1e-12)
def spatial_sd(x):
 x=np.asarray(x);n=x.shape[-2]
 if n<2:return np.nan
 return np.sqrt(np.sum((x-x.mean(-2,keepdims=True))**2,axis=(-2,-1))/(n-1))
def ci(values):
 a=np.asarray(values);a=a[np.isfinite(a)]
 return (float(np.quantile(a,.025)),float(np.quantile(a,.975)),len(a)) if len(a) else (None,None,0)
def pointmap(obj):return {p['label']:np.array(p['position'],float) for p in obj['points'] if p['status'] in PRESENT}
def collect(root=ROOT):
 from coleta import scan_sessions
 found,missing,issues=scan_sessions(root)
 errors=[q for q in issues if q['tipo']!='intervalo']
 if errors:raise ValueError('Sessões inválidas: '+json.dumps(errors,ensure_ascii=False))
 return found,missing,issues
def analyze(root=ROOT):
 from coleta import readiness
 report,found=readiness(root);missing=report['missing'];issues=report['invalid_sessions_or_intervals']
 if report['blockers']:raise ValueError('Pré-requisitos humanos/técnicos ausentes: '+json.dumps(report['blockers'],ensure_ascii=False))
 if missing or issues:raise ValueError(f'Coleta incompleta ou intervalo inválido: {len(missing)} sessões ausentes; {len(issues)} intervalos inválidos. Use --check.')
 transforms=load(root/'transformacoes_congeladas.json')['IDs']
 with (root/'amostra_coordenacao.csv').open() as f:labels={r['ID']:int(r['grupo']) for r in csv.DictReader(f)}
 data={k:pointmap(o) for k,o in found.items()};definitions=[p for p in protocol(root)['landmarks'] if p.get('enabled',True)];rng=np.random.default_rng(SEED);out=root/'resultados';out.mkdir(exist_ok=True);reliability=[];distances=[];missingrows=[]
 for (i,r,s),obj in found.items():
  for p in obj['points']:
   if p['status'] not in PRESENT:missingrows.append({'ID':i,'avaliador':r,'sessao':s,'landmark':p['label'],'motivo':p['status']})
 comparisons=[('inter','A1_T1','A2_T1')]+[('intra_'+r,r+'_T1',r+'_T2') for r in ['A1','A2']]
 # Grandezas escalares: não confundir distância 3D entre incisivos com overjet clínico.
 def scalars(points):
  result={}
  for name,a,b in [('largura_molar_superior','U6_R','U6_L'),('largura_molar_inferior','L6_R','L6_L'),('fissura_anterior_exploratoria','F_A_MAIOR','F_A_MENOR'),('fissura_posterior_exploratoria','F_P_MAIOR','F_P_MENOR'),('distancia_incisivos_R_3D','U1_R','L1_R'),('distancia_incisivos_L_3D','U1_L','L1_L')]:
   if a in points and b in points:result[name]=float(np.linalg.norm(points[a]-points[b]))
  for side in ['R','L']:
   a,b='U1_'+side,'L1_'+side
   if a in points and b in points:result['proxy_overjet_AP_'+side]=float(-(points[a]-points[b])[1])
  return result
 scalar_values={k:scalars(v) for k,v in data.items()};availability=[]
 for comparison,one,two in comparisons:
  r1,s1=one.split('_');r2,s2=two.split('_');available=sorted(i for i in labels if (i,r1,s1) in data and (i,r2,s2) in data)
  for group in ['todos',1,2,3]:
   selected=[i for i in available if group=='todos' or labels[i]==group]
   for lm in definitions:
    label=lm['label'];ids=[i for i in selected if label in data[(i,r1,s1)] and label in data[(i,r2,s2)]];n=len(ids)
    availability.append({'comparacao':comparison,'grupo':group,'landmark':label,'n_conteudos_elegiveis':len(selected),'n_conteudos_validos':n,'n_conteudos_com_ausencia':len(selected)-n,'ausencias_observacao_1':sum(label not in data[(i,r1,s1)] for i in selected),'ausencias_observacao_2':sum(label not in data[(i,r2,s2)] for i in selected),'exploratorio':n<10})
    if n==0:
     reliability.append({'comparacao':comparison,'grupo':group,'variavel':label,'tipo':'distancia_3D_mm','n_conteudos':0,'estimativa':None,'IC95_inf':None,'IC95_sup':None,'bootstrap_validos':0,'nota':'nenhum par de pontos disponíveis'});continue
    a=np.stack([data[(i,r1,s1)][label] for i in ids]);b=np.stack([data[(i,r2,s2)][label] for i in ids]);d=np.linalg.norm(a-b,axis=1);ix=rng.integers(n,size=(B,n));lo,hi,valid=ci(d[ix].mean(1));reliability.append({'comparacao':comparison,'grupo':group,'variavel':label,'tipo':'distancia_3D_mm','n_conteudos':n,'estimativa':float(d.mean()),'IC95_inf':lo,'IC95_sup':hi,'bootstrap_validos':valid,'nota':'distância média, não erro contra verdade anatômica'+('; n<10 exploratório' if n<10 else '')})
    if group=='todos':
     for i,dd in zip(ids,d):distances.append({'ID':i,'grupo':labels[i],'comparacao':comparison,'landmark':label,'distancia_mm':float(dd)})
    for axis in range(3):
     value=float(icc_absolute(np.stack([a[:,axis],b[:,axis]],1))) if n>=3 else np.nan;draws=icc_absolute(np.stack([a[:,axis],b[:,axis]],1)[ix]) if n>=3 else [];lo,hi,valid=ci(draws);reliability.append({'comparacao':comparison,'grupo':group,'variavel':label+'_C'+str(axis+1),'tipo':'ICC_A_1_absoluto','n_conteudos':n,'estimativa':value if np.isfinite(value) else None,'IC95_inf':lo,'IC95_sup':hi,'bootstrap_validos':valid,'nota':('aleatório inter; misto intra; negativo preservado; n<10 exploratório' if n<10 else 'aleatório inter; misto intra; negativo preservado')+('; IC instável' if valid<.8*B else '')})
   scalar_names=sorted({k for i in selected for k in scalar_values[(i,r1,s1)]}|{k for i in selected for k in scalar_values[(i,r2,s2)]})
   for name in scalar_names:
    ids=[i for i in selected if name in scalar_values[(i,r1,s1)] and name in scalar_values[(i,r2,s2)]];n=len(ids)
    if not n:continue
    y=np.array([[scalar_values[(i,r1,s1)][name],scalar_values[(i,r2,s2)][name]] for i in ids]);ix=rng.integers(n,size=(B,n));v=float(icc_absolute(y)) if n>=3 else np.nan;lo,hi,valid=ci(icc_absolute(y[ix]) if n>=3 else []);reliability.append({'comparacao':comparison,'grupo':group,'variavel':name,'tipo':'ICC_A_1_absoluto_medida_escalar','n_conteudos':n,'estimativa':v if np.isfinite(v) else None,'IC95_inf':lo,'IC95_sup':hi,'bootstrap_validos':valid,'nota':'proxy AP não é overjet clínico validado; mesmos pontos não são independentes'})
 save_csv(out/'confiabilidade.csv',reliability);save_csv(out/'disponibilidade_por_landmark.csv',availability)
 save_csv(out/'distancias_por_ID.csv',distances,fieldnames=['ID','grupo','comparacao','landmark','distancia_mm'])
 save_csv(out/'ausencias.csv',missingrows,fieldnames=['ID','avaliador','sessao','landmark','motivo'])
 # Consenso de coordenadas T1 A1/A2 é média após marcação independente; não é GT.
 dispersion=[];contrasts=[];consensus=[]
 for lm in definitions:
  label=lm['label'];valid={i:(data[(i,'A1','T1')][label]+data[(i,'A2','T1')][label])/2 for i in labels if label in data[(i,'A1','T1')] and label in data[(i,'A2','T1')]}
  for group in ['todos',1,2,3]:
   ids=sorted(i for i in valid if group=='todos' or labels[i]==group);n=len(ids)
   if n<2:
    for centering in ['coordenadas_completas','centroide_geometrico_removido']:
     for method in ['nenhuma','controle','anatomica','multi5_rmse']:
      dispersion.append({'landmark':label,'grupo':group,'n_conteudos':n,'normalizacao':method,'relatorio':centering,'desvio_espacial_mm':None,'IC95_inf':None,'IC95_sup':None,'bootstrap_validos':0,'observacao':'n<2: dispersão não estimável; ausência não imputada'})
      if method!='nenhuma':contrasts.append({'landmark':label,'grupo':group,'n_conteudos':n,'normalizacao':method,'relatorio':centering,'delta_desvio_mm':None,'IC95_inf':None,'IC95_sup':None,'bootstrap_validos':0,'interpretacao':'n<2: contraste não estimável; ausência não imputada'})
    continue
   ix=rng.integers(n,size=(B,n))
   for centering in ['coordenadas_completas','centroide_geometrico_removido']:
    arrays={}
    for method in ['nenhuma','controle','anatomica','multi5_rmse']:
     x=np.stack([convert_point(valid[i],i,method,transforms) for i in ids]);T=[np.array(transforms[i]['methods'][method]) for i in ids]
     if centering=='centroide_geometrico_removido':x-=np.stack([M[:3,:3]@np.array(transforms[i]['raw_geometry_centroid'])+M[:3,3] for i,M in zip(ids,T)])
     arrays[method]=x;stat=float(spatial_sd(x));lo,hi,count=ci(spatial_sd(x[ix]));dispersion.append({'landmark':label,'grupo':group,'n_conteudos':n,'normalizacao':method,'relatorio':centering,'desvio_espacial_mm':stat,'IC95_inf':lo,'IC95_sup':hi,'bootstrap_validos':count,'observacao':'sqrt(trace(cov)), sem Procrustes; mistura morfologia e pose'+('; n<10 exploratório' if n<10 else '')})
    original=spatial_sd(arrays['nenhuma'][ix])
    for method in ['controle','anatomica','multi5_rmse']:
     draws=spatial_sd(arrays[method][ix])-original;lo,hi,count=ci(draws);contrasts.append({'landmark':label,'grupo':group,'n_conteudos':n,'normalizacao':method,'relatorio':centering,'delta_desvio_mm':float(spatial_sd(arrays[method])-spatial_sd(arrays['nenhuma'])),'IC95_inf':lo,'IC95_sup':hi,'bootstrap_validos':count,'interpretacao':'diferença pareada contra nenhuma; não mede correção anatômica'+('; n<10 exploratório' if n<10 else '')})
  for i,p in valid.items():consensus.append({'ID':i,'landmark':label,'x_C_mm':p[0],'y_C_mm':p[1],'z_C_mm':p[2],'definicao':'média A1/A2 T1; referência humana, não verdade absoluta'})
 if dispersion:save_csv(out/'dispersao_landmarks.csv',dispersion);save_csv(out/'dispersao_diferencas_pareadas.csv',contrasts)
 save_csv(out/'referencia_humana_T1.csv',consensus,fieldnames=['ID','landmark','x_C_mm','y_C_mm','z_C_mm','definicao'])
 result={'status':'ANALISE_HUMANA_CONCLUIDA','sessions':len(found),'contents':len(labels),'bootstrap_unit':'conteúdo-paciente; não misturar landmarks como amostras independentes','bootstrap_replicates':B,'seed':SEED,'normalization_rules_updated':False,'detector_optional_started':False,'units':'mm_assumed_from_STL','protocol_sha256':sha(protocol_path(root))};(out/'status.json').write_text(json.dumps(result,indent=2));return result
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');a=parser.parse_args()
 if a.check:
  from coleta import export_check
  print(json.dumps(export_check(),ensure_ascii=False,indent=2));return
 print(json.dumps(analyze(),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
