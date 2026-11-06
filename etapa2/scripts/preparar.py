"""Cópias, triagem de articulação nativa e template pareado único."""
from common import *
import collections,shutil

def main():
    inventory=list(csv.DictReader((ROOT/'inventario.csv').open()));groups=collections.defaultdict(list)
    for i,r in enumerate(inventory):r['stl_id']=f'STL{i+1:03d}';groups[(r['grupo'],r['pasta_paciente'])].append(r)
    pairs=[];excluded=[];manifest=[];art=[]
    for key,rs in sorted(groups.items()):
        arches={a:{r['sha256']:r for r in rs if r['arcada']==a} for a in ['superior','inferior']}
        if any(len(arches[a])!=1 for a in arches):
            excluded.append({'paciente':'/'.join(key),'motivo':'sem um conteúdo superior e um inferior identificados inequivocamente','arquivos':[r['arquivo'] for r in rs]});continue
        identifier=f'P{len(pairs)+1:03d}';p={'id':identifier,'paciente':'/'.join(key)}
        for category in ['superior','inferior','registro_mordida']:
            options=[r for r in rs if r['arcada']==category]
            if not options:continue
            r=options[0];source=ROOT/'etapa1/copias'/r['arquivo'];target=OUT/'copias'/identifier/f'{category}.stl';target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(source,target)
            assert digest(source)==digest(target)==r['sha256']
            manifest.append({'id':identifier,'categoria':category,'fonte':str(source),'original':str(ROOT/'dados'/r['arquivo']),'copia':str(target.relative_to(OUT)),'sha256':r['sha256']})
            p[category]={'arquivo':str(target.relative_to(OUT)),'fonte_inventario':r['arquivo'],'sha256':r['sha256'],'stl_id':r['stl_id']}
        upper=read_triangles(OUT/p['superior']['arquivo']);lower=read_triangles(OUT/p['inferior']['arquivo'])
        details=proximity(upper,lower)
        lo1=upper.reshape(-1,3).min(0);hi1=upper.reshape(-1,3).max(0);lo2=lower.reshape(-1,3).min(0);hi2=lower.reshape(-1,3).max(0)
        overlaps=np.maximum(0,np.minimum(hi1,hi2)-np.maximum(lo1,lo2));length_ratios=overlaps/np.minimum(hi1-lo1,hi2-lo2)
        us=sample_surface(upper,12000,SEED);ls=sample_surface(lower,12000,SEED+1);d=us.mean(0)-ls.mean(0);mean_dims=((hi1-lo1)+(hi2-lo2))/2
        reasons=[]
        if details['distancia_min_aproximada']>1.5:reasons.append('distância mínima aproximada >1,5')
        if min(length_ratios[:2])<.65:reasons.append('pouca sobreposição XY de bounding boxes')
        if abs(d[1])/mean_dims[1]>.25:reasons.append('deslocamento AP nativo >25% da profundidade média')
        if abs(d[0])/mean_dims[0]>.15:reasons.append('deslocamento lateral nativo >15% da largura média')
        if d[2]<=0:reasons.append('ordem vertical nativa superior/inferior invertida')
        plausible=not reasons
        record={'id':identifier,'paciente':p['paciente'],**details,
            'bbox_intersecao_X':float(overlaps[0]),'bbox_intersecao_Y':float(overlaps[1]),'bbox_intersecao_Z':float(overlaps[2]),
            'bbox_fracao_intersecao_X':float(length_ratios[0]),'bbox_fracao_intersecao_Y':float(length_ratios[1]),'bbox_fracao_intersecao_Z':float(length_ratios[2]),
            'bbox_volume_intersecao':float(np.prod(overlaps)),'bbox_volume_intersecao_fracao_menor':float(np.prod(overlaps)/min(np.prod(hi1-lo1),np.prod(hi2-lo2))),
            'delta_centroides_X':float(d[0]),'delta_centroides_AP_Y':float(d[1]),'delta_centroides_vertical_Z':float(d[2]),
            'delta_AP_fracao_profundidade_media':float(abs(d[1])/mean_dims[1]),'parece_articulado':plausible,
            'registro_mordida_disponivel':'registro_mordida' in p,'status':'PARECE_ARTICULADO_TRIAGEM' if plausible else 'REQUER_REGISTRO_MANUAL',
            'observacoes':'; '.join(reasons) if reasons else 'proximidade e posição relativa compatíveis; não confirma contato oclusal anatômico'}
        if not plausible and 'registro_mordida' in p:
            # Registro é usado como evidência de posição nativa, sem mover arcadas separadamente.
            bite=read_triangles(OUT/p['registro_mordida']['arquivo']);cloud_bite=sample_surface(bite,20000,SEED+2)
            dsu=dist_to_mesh(cloud_bite,scene(upper));dsl=dist_to_mesh(cloud_bite,scene(lower))
            nearu=float(np.mean(dsu<=1));nearl=float(np.mean(dsl<=1));record['observacoes']+=f'; registro nativo: fração a 1 unidade superior={nearu:.4f}, inferior={nearl:.4f}'
            # Só resgata se registro sustenta ambas e os checks globais continuam adequados.
            if min(nearu,nearl)>=.05 and min(length_ratios[:2])>=.65 and abs(d[1])/mean_dims[1]<=.25 and d[2]>0:
                record['parece_articulado']=True;record['status']='COMPATIVEL_COM_REGISTRO_NATIVO_REVISAR';record['observacoes']+='; registro usado como evidência, sem reconstrução independente'
            else:record['observacoes']+='; registro não sustenta articulação nativa; reconstrução requer registro manual'
        p['parece_articulado']=record['parece_articulado'];p['status_articulacao']=record['status'];p['motivos_articulacao']=record['observacoes']
        p['superior_axes']=json.loads(next(r['pca_eixos_colunas'] for r in rs if r['arcada']=='superior'))
        # Pré-calcula duas decimações reais para variar a geometria entre ensaios.
        cache=OUT/'cache'/identifier;cache.mkdir(parents=True,exist_ok=True)
        for a,tri in [('superior',upper),('inferior',lower)]:
            for level,fraction in [('leve',.5),('forte',.2)]:
                path=cache/f'{a}_{level}.npz'
                if not path.exists():
                    target=min(30000,max(4000,int(len(tri)*fraction)));dec=simplify(tri,target);np.savez_compressed(path,tri=dec)
                if level=='forte':np.savez_compressed(cache/f'{a}_preview.npz',tri=np.load(path)['tri'])
        pairs.append(p);art.append(record)
        save_json('pares.json',pairs);save_json('manifesto_copias.json',manifest);save_csv('articulacao.csv',art)
        print(f'{len(pairs)}/69 {identifier} min={details["distancia_min_aproximada"]:.5f} articulado={record["parece_articulado"]}',flush=True)
    save_json('pastas_excluidas.json',excluded)
    candidates=[];seen=set()
    for p in pairs:
        h=(p['superior']['sha256'],p['inferior']['sha256'])
        if p['parece_articulado'] and h not in seen:candidates.append(p);seen.add(h)
    assert candidates,'Nenhum par elegível a template provisório'
    distances=np.zeros((len(candidates),len(candidates)))
    for i,j in itertools.combinations(range(len(candidates)),2):distances[i,j]=distances[j,i]=angular_axes(np.array(candidates[i]['superior_axes']),np.array(candidates[j]['superior_axes']))
    idx=int(np.argmin(distances.sum(1)));template=candidates[idx]
    for a in ['superior','inferior']:shutil.copy2(OUT/template[a]['arquivo'],OUT/'templates'/f'{a}.stl')
    save_json('templates/selecao.json',{'id':template['id'],'paciente':template['paciente'],'metodo':'medoide angular dos eixos PCA superiores entre pares plausivelmente articulados, deduplicados por hashes de ambas as arcadas','distancia_media_graus':float(distances[idx].mean()),'pares_unicos_elegiveis':len(candidates),'superior':template['superior'],'inferior':template['inferior']})
    rng=np.random.default_rng(SEED)
    selected_original=sorted(rng.choice([p['id'] for p in pairs],15,replace=False).tolist())
    selected_normalized=sorted(rng.choice([p['id'] for p in pairs],20,replace=False).tolist())
    save_json('selecao_visual.json',{'seed':SEED,'originais_15':selected_original,'normalizados_20':selected_normalized,'universo':'69 pares por pasta; sem reposição dentro de cada seleção; inclui duplicatas de conteúdo explicitadas'})
    print('PREPARACAO_CONCLUIDA',len(pairs),'plausíveis',sum(p['parece_articulado'] for p in pairs),'template',template['id'],flush=True)
if __name__=='__main__':main()
