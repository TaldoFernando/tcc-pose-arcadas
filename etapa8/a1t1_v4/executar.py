"""Execução geométrica A1/T1; valida entradas antigas sem reescrever seus contratos.

Não estima confiabilidade, não treina detectores e não reabre o teste de ML.
Congelar primeiro; executar depois. Uma nova entrada exige outra versão de execução.
"""
from pathlib import Path
import argparse
import collections
import datetime
import json
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
E8 = HERE.parent
sys.path.insert(0, str(E8))
from e8_common import (load, sha, protocol, protocol_path, verify_frozen,
                       validate_template, validate_annotation, rigid_matrix,
                       convert_point, save_csv, PRESENT)

METHODS = ['nenhuma', 'controle', 'anatomica', 'multi5_rmse']
SEED = 20261110
B = 10000


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def read_csv(path):
    import csv
    with Path(path).open() as file:
        return list(csv.DictReader(file))


def audit_annotations(root=E8):
    """Ausência de A2/T2 nunca bloqueia; entrada A1/T1 inválida sempre bloqueia."""
    root = Path(root)
    verify_frozen(root)
    definitions = protocol(root)
    validate_template(root)
    original = load(root / 'plano.json')
    transforms = load(root / 'transformacoes_congeladas.json')['IDs']
    expected = set(original['study_IDs'])
    if len(expected) != len(original['study_IDs']):
        raise ValueError('IDs duplicados no plano original.')
    excluded = set(original['pilot_development_IDs']) | {original['template_ID']}
    if expected & excluded:
        raise ValueError('Piloto/template na amostra principal.')
    found, paths, ignored = {}, {}, []
    for path in sorted((root / 'marcacoes').glob('*.json')):
        if path.name.endswith('.mrk.json'):
            continue
        obj = load(path)
        if (obj.get('avaliador'), obj.get('sessao')) != ('A1', 'T1'):
            ignored.append({'ID': obj.get('ID'), 'avaliador': obj.get('avaliador'),
                            'sessao': obj.get('sessao'), 'motivo': 'fora da execução A1/T1'})
            continue
        identifier = obj.get('ID')
        if identifier not in expected:
            raise ValueError('A1/T1 fora do plano principal: ' + str(identifier))
        if identifier in found:
            raise ValueError('Exportação A1/T1 duplicada: ' + identifier)
        validate_annotation(obj, root)
        if obj.get('protocol_file') not in (None, protocol_path(root).name):
            raise ValueError('Nome do perfil incompatível: ' + identifier)
        for method in METHODS:
            rigid_matrix(transforms[identifier]['methods'][method])
        centroid = np.asarray(transforms[identifier]['raw_geometry_centroid'], float)
        if centroid.shape != (3,) or not np.isfinite(centroid).all():
            raise ValueError('Centroide inválido: ' + identifier)
        found[identifier], paths[identifier] = obj, path
    # Conteúdo idêntico não recebe peso independente na geometria.
    groups = {r['ID']: r for r in read_csv(root / 'amostra_coordenacao.csv')}
    content_ids = [groups[i].get('ID_conteudo', i) for i in found]
    if len(content_ids) != len(set(content_ids)):
        raise ValueError('Conteúdo duplicado na análise.')
    summary = {
        'confiabilidade': 'nao_avaliada', 'avaliadores': ['A1'], 'sessoes': ['T1'],
        'A2_exigido': False, 'funcao_independente_A2_definida': False,
        'T2_exigido': False, 'intervalo_14_dias_exigido': False, 'ICC_exigido': False,
        'principais_previstos_plano_original': len(expected), 'principais_validos': len(found),
        'IDs_validos': sorted(found), 'IDs_faltantes_plano_original': sorted(expected - set(found)),
        'analise_parcial': bool(expected - set(found)),
        'pilotos_fora_analise': original['pilot_development_IDs'],
        'template_fora_analise': original['template_ID'],
        'sessoes_ignoradas': ignored,
        'por_grupo': dict(collections.Counter(groups[i]['grupo'] for i in found)),
        'ready_geometria': bool(found),
    }
    historical = []
    for identifier in original['pilot_development_IDs']:
        path = root / 'piloto_marcacoes' / f'{identifier}_A1_T1.json'
        if path.exists():
            obj = validate_annotation(load(path), root, phase='pilot')
            historical.append({'ID': identifier, 'n_pontos_perfil_historico': len(obj['points']),
                               'sha256': sha(path), 'incluido_geometria_principal': False})
    summary['pilotos_exportados'] = historical
    summary['template_validado'] = True
    # V3 descreve trabalho concluído, sem redefinir silenciosamente os 24 originais.
    v3 = root / 'coleta24_v3/plano_trabalho.json'
    if v3.exists():
        p = load(v3)
        summary['comparacao_V3'] = {
            'principais_previstos': len(p['assisted_main_IDs']),
            'faltantes': sorted(set(p['assisted_main_IDs']) - set(found)),
            'retirados_da_carga_anterior': p['excluded_future_IDs'],
            'nota': '21/21 na carga V3; 21/24 e parcial em relação ao plano original.'}
    return summary, found, paths, definitions, transforms, groups


def audit_partition(eligible, split, folds):
    """Mantém aliases, hashes de conteúdo e blocos de paciente na mesma partição."""
    lookup = {c['ID']: c for c in eligible}
    dev, test = set(split['dev_IDs']), set(split['test_IDs'])
    if dev & test or dev | test != set(lookup):
        raise ValueError('Partições 5C inconsistentes.')
    alias_to_id, content_to_id = {}, {}
    for c in eligible:
        for alias in c['aliases']:
            if alias in alias_to_id and alias_to_id[alias] != c['ID']:
                raise ValueError('Alias em conteúdos distintos.')
            alias_to_id[alias] = c['ID']
        if c['conteudo_hash'] in content_to_id:
            raise ValueError('Conteúdo idêntico representado mais de uma vez.')
        content_to_id[c['conteudo_hash']] = c['ID']
    def disjoint(a, b):
        if a & b:
            raise ValueError('IDs cruzam partições.')
        for key in ['conteudo_hash', 'bloco_paciente_proxy']:
            if {lookup[i][key] for i in a} & {lookup[i][key] for i in b}:
                raise ValueError('Conteúdo/paciente cruza partições: ' + key)
    disjoint(dev, test)
    for f in folds:
        train, val = set(f['train_IDs']), set(f['val_IDs'])
        if train | val != dev or (train | val) & test:
            raise ValueError('Fold fora do desenvolvimento.')
        disjoint(train, val)
    return lookup, alias_to_id


def audit_ml(root, found):
    project = Path(root).parent
    ml = project / 'etapa5c'
    for name in ['congelamento.json', 'congelamento_execucao.json', 'liberacao_final.json']:
        for relative, digest in load(ml / name)['files'].items():
            if sha(project / relative) != digest:
                raise ValueError('Hash ML incompatível: ' + relative)
    eligible, split, folds = [load(ml / name) for name in
                             ['conteudos_elegiveis.json', 'divisao.json', 'folds_CV.json']]
    lookup, aliases = audit_partition(eligible, split, folds)
    available = set(found)
    annotated = {aliases[i] for i in available if i in aliases}
    dev, test = set(split['dev_IDs']), set(split['test_IDs'])
    trainlog = load(ml / 'resultados/treinamento_CV.json')
    if len(folds) != 20 or len(trainlog) != 20:
        raise ValueError('CV existente incompleta.')
    for f, log in zip(folds, trainlog):
        if set(log['train_IDs']) != set(f['train_IDs']) or set(log['val_IDs']) != set(f['val_IDs']):
            raise ValueError('Treino registrado diverge do fold.')
    # Verifica também os IDs das predições existentes, sem recalcular o teste.
    import csv
    oof_ids, validation_sets = set(), {(f['repeticao'], f['fold']): set(f['val_IDs']) for f in folds}
    with (ml / 'resultados/predicoes_OOF.csv').open() as file:
        for row in csv.DictReader(file):
            if row['ID'] not in validation_sets[(int(row['repeticao']), int(row['fold']))]:
                raise ValueError('Predição OOF fora da validação.')
            oof_ids.add(row['ID'])
    final_rows = read_csv(ml / 'resultados/predicoes_teste_final.csv')
    if oof_ids != dev or {r['ID'] for r in final_rows} != test:
        raise ValueError('IDs das predições não correspondem à divisão.')
    release, opened = load(ml / 'liberacao_final.json'), load(ml / 'teste_bloqueado/abertura.json')
    if (opened['sha256_liberacao_final'] != sha(ml / 'liberacao_final.json') or
            datetime.datetime.fromisoformat(release['utc']) >= datetime.datetime.fromisoformat(opened['utc'])):
        raise ValueError('Congelamento não precede abertura do teste.')
    return {
        'modelo': 'modelo substituto; não Goslon AI',
        'desenvolvimento': len(dev), 'teste': len(test), 'CV_ajustes_existentes': len(trainlog),
        'teste_ja_aberto': True, 'abertura_registrada_utc': opened['utc'],
        'configuracao_congelada_utc': release['utc'], 'reexecutou_treino_ou_teste': False,
        'reuso_nesta_execucao': 'auditoria e citação de resultados existentes; sem novas predições ou ajuste',
        'criterio_selecao_existente': release['model_choice'],
        'validacao': '4 folds × 5 seeds; configuração fixa previamente, sem seleção por desempenho do teste',
        'primario_teste_existente': load(ml / 'resultados/primario_teste.json'),
        'marcacoes_principais_V2_dev_IDs': sorted(annotated & dev),
        'marcacoes_principais_V2_teste_IDs': sorted(annotated & test),
        'marcacoes_principais_excluidas_ML_IDs': sorted(available - set(aliases)),
        'detector_landmarks': {
            'status': 'NAO_TREINADO', 'motivo': 'experimento e configuração próprios ainda não definidos',
            'marcacoes_V2_dev_disponiveis': len(annotated & dev),
            'IDs_dev_sem_marcacao_principal_V2': sorted(dev - annotated),
            'IDs_teste_reservados': sorted(test),
            'pilotos_historicos_misturados_ao_treino': False,
            'P016': 'template manual disponível no desenvolvimento; separado da análise principal',
            'nota': 'nem todas as marcações estão no teste 5C. O teste geométrico original e o teste 5C são experimentos diferentes.'},
        'restricoes': [
            'Identidade clínica não confirmada: agrupamento por conteúdo e bloco proxy; visitas diferentes podem escapar.',
            'Nenhuma marcação de teste 5C é usada para treino/seleção do classificador ou futuro detector.',
            'Resultados geométricos não escolhem configurações para o teste ML já aberto.',
            'Banco global na CV existente; sensibilidade sem cinco templates na pontuação, não equivale a refazer banco por fold.',
            'Exposição histórica: teste 5C não é validação externa/inédita; câmeras originais PLACEHOLDER.'],
    }, lookup


def spatial_sd(x):
    x = np.asarray(x)
    return np.sqrt(np.sum((x - x.mean(axis=-2, keepdims=True)) ** 2, axis=(-2, -1)) / (x.shape[-2] - 1))


def geometric_tables(found, definitions, transforms, groups, b=B, seed=SEED):
    points = {i: {p['label']: p for p in obj['points']} for i, obj in found.items()}
    availability, missing, reference, dispersion, contrasts, by_id = [], [], [], [], [], []
    rng = np.random.default_rng(seed)
    for i in sorted(found):
        pp = points[i]
        by_id.append({'ID': i, 'grupo': groups[i]['grupo'], 'n_disponiveis': sum(p['status'] in PRESENT for p in pp.values()),
                      'n_ausentes': sum(p['status'] not in PRESENT for p in pp.values()),
                      'referencia': 'A1/T1; assistida e revisada; confiabilidade não avaliada'})
        for label, p in pp.items():
            if p['status'] in PRESENT:
                reference.append({'ID': i, 'landmark': label, 'x_C_mm': p['position'][0],
                                  'y_C_mm': p['position'][1], 'z_C_mm': p['position'][2], 'status': p['status']})
            else:
                missing.append({'ID': i, 'grupo': groups[i]['grupo'], 'landmark': label, 'motivo': p['status']})
    for lm in definitions['landmarks']:
        if not lm.get('enabled', True):
            continue
        label = lm['label']
        for group in ['todos', '1', '2', '3']:
            selected = sorted(i for i in found if group == 'todos' or groups[i]['grupo'] == group)
            ids = [i for i in selected if points[i][label]['status'] in PRESENT]
            n = len(ids)
            availability.append({'landmark': label, 'grupo': group, 'n_moldes': len(selected),
                                 'n_disponiveis': n, 'n_ausentes': len(selected) - n})
            ix = rng.integers(n, size=(b, n)) if n >= 2 else None
            for centering in ['coordenadas_completas', 'centroide_geometrico_removido']:
                estimates, draws = {}, {}
                for method in METHODS:
                    row = {'landmark': label, 'grupo': group, 'n_conteudos': n, 'normalizacao': method,
                           'relatorio': centering, 'desvio_espacial_mm': None, 'IC95_inf': None,
                           'IC95_sup': None, 'exploratorio': True}
                    if n >= 2:
                        x = np.stack([convert_point(points[i][label]['position'], i, method, transforms) for i in ids])
                        if centering == 'centroide_geometrico_removido':
                            matrices = [rigid_matrix(transforms[i]['methods'][method]) for i in ids]
                            x -= np.stack([m[:3, :3] @ np.asarray(transforms[i]['raw_geometry_centroid']) + m[:3, 3]
                                           for i, m in zip(ids, matrices)])
                        estimates[method], draws[method] = float(spatial_sd(x)), spatial_sd(x[ix])
                        lo, hi = np.quantile(draws[method], [.025, .975])
                        row.update(desvio_espacial_mm=estimates[method], IC95_inf=float(lo), IC95_sup=float(hi))
                    dispersion.append(row)
                for method in METHODS[1:]:
                    row = {'landmark': label, 'grupo': group, 'n_conteudos': n, 'normalizacao': method,
                           'relatorio': centering, 'delta_desvio_mm': None, 'IC95_inf': None, 'IC95_sup': None}
                    if n >= 2:
                        lo, hi = np.quantile(draws[method] - draws['nenhuma'], [.025, .975])
                        row.update(delta_desvio_mm=estimates[method] - estimates['nenhuma'], IC95_inf=float(lo), IC95_sup=float(hi))
                    contrasts.append(row)
    return {'disponibilidade': availability, 'ausencias': missing, 'referencia_A1_T1': reference,
            'dispersao': dispersion, 'contrastes_pareados': contrasts, 'por_ID': by_id}


def input_files(root=E8):
    root = Path(root)
    project = root.parent
    files = {root / name for name in ['plano.json', 'congelamento.json', 'protocolo_validado.json',
             'transformacoes_congeladas.json', 'amostra_coordenacao.csv', 'template/template_validado.json']}
    files.add(protocol_path(root))
    files.add(root / 'coleta24_v3/plano_trabalho.json')
    files.update(root / name for name in load(root / 'protocolo_validado.json')['code_sha256'])
    for sub in ['marcacoes', 'piloto_marcacoes', 'referencias_piloto']:
        files.update((root / sub).glob('*.json'))
    files.update(project / n for n in load(root / 'congelamento.json')['files'])
    for name in ['congelamento.json', 'congelamento_execucao.json', 'liberacao_final.json']:
        manifest = project / 'etapa5c' / name
        files.add(manifest)
        files.update(project / n for n in load(manifest)['files'])
    files.update((project / 'etapa5c/resultados').glob('*.json'))
    files.update((project / 'etapa5c/resultados').glob('*.csv'))
    files.update(project / 'etapa5c' / n for n in ['conteudos_elegiveis.json', 'teste_bloqueado/abertura.json',
                 'teste_bloqueado/entradas.json', 'exclusoes_rotulos.csv'])
    # Verifica imutabilidade das cópias-fonte de todas as arcadas; não modifica STL.
    for p in load(project / 'etapa5/pares_ids.json'):
        for arch in ['superior', 'inferior']:
            source = project / 'etapa5' / p[arch]['arquivo']
            if sha(source) != p[arch]['sha256']:
                raise ValueError('STL fonte alterado: ' + p['id'] + '/' + arch)
            files.add(source)
    files.update([HERE / 'executar.py', HERE / 'plano_execucao.json', E8 / 'tests/test_A1_T1.py'])
    return sorted(files)


def freeze():
    destination = HERE / 'congelamento.json'
    if destination.exists():
        raise ValueError('Execução já congelada; não sobrescrever. Use nova versão para novos dados.')
    audit_annotations()
    digest = {str(p.relative_to(E8.parent)): sha(p) for p in input_files()}
    save(destination, {'version': 'A1_T1_V4', 'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       'before_geometric_computation': True, 'after_human_collection': True,
                       'bootstrap_seed': SEED, 'bootstrap_replicates': B, 'files': digest,
                       'confiabilidade': 'nao_avaliada', 'normalization_changed': False})


def verify_execution():
    lock = load(HERE / 'congelamento.json')
    for name, digest in lock['files'].items():
        if sha(E8.parent / name) != digest:
            raise ValueError('Entrada da execução mudou: ' + name)
    current = {str(p.relative_to(E8.parent)) for p in input_files()}
    if current != set(lock['files']):
        raise ValueError('Inventário de entradas mudou; exige nova versão.')
    return lock


def run():
    lock = verify_execution()
    out = HERE / 'resultados'
    if out.exists():
        raise ValueError('Resultados já existem; preservar esta execução.')
    summary, found, paths, definitions, transforms, groups = audit_annotations()
    if not summary['ready_geometria']:
        raise ValueError('Nenhum A1/T1 válido.')
    ml, lookup = audit_ml(E8, found)
    tables = geometric_tables(found, definitions, transforms, groups)
    verify_execution()
    out.mkdir()
    for name, rows in tables.items():
        headers = {'ausencias': ['ID', 'grupo', 'landmark', 'motivo'],
                   'referencia_A1_T1': ['ID', 'landmark', 'x_C_mm', 'y_C_mm', 'z_C_mm', 'status']}
        save_csv(out / (name + '.csv'), rows, fieldnames=headers.get(name))
    save(out / 'auditoria_coleta.json', summary)
    save(out / 'separacao_ML.json', ml)
    # Inventário por experimento: o CSV geométrico completo nunca é uma lista de treino ML.
    mapping = []
    split = load(E8.parent / 'etapa5c/divisao.json')
    alias_map = {a: c['ID'] for c in lookup.values() for a in c['aliases']}
    roles = [(i, 'principal') for i in found]
    roles += [(i, 'piloto_historico') for i in summary['pilotos_fora_analise']]
    roles += [(summary['template_fora_analise'], 'template')]
    for i, role in sorted(roles):
        content = alias_map.get(i)
        partition = ('desenvolvimento' if content in split['dev_IDs'] else
                     'teste' if content in split['test_IDs'] else 'excluido_por_conflito_rotulo')
        mapping.append({'ID': i, 'papel_etapa8': role, 'particao_5C': partition,
                        'permitido_treino_ML': partition == 'desenvolvimento',
                        'perfil': 'V2' if role != 'piloto_historico' else 'historico_nao_harmonizado'})
    save_csv(out / 'IDs_por_experimento.csv', mapping)
    missing = set(ml['detector_landmarks']['IDs_dev_sem_marcacao_principal_V2'])
    # Lista por ponto, distinguindo falta de sessão de ausência explicitamente anotada.
    gaps = []
    for i in sorted(load(E8.parent / 'etapa5c/divisao.json')['dev_IDs']):
        annotated = {p['label']: p for p in found[i]['points']} if i in found else {}
        for lm in definitions['landmarks']:
            if not lm.get('enabled', True):
                continue
            point = annotated.get(lm['label'])
            if point is None or point['status'] not in PRESENT:
                gaps.append({'ID': i, 'landmark': lm['label'], 'situacao':
                             'sem_sessao_principal_V2' if i in missing else point['status'],
                             'nota': 'P016 separado como template' if i == 'P016' else 'não imputar coordenadas'})
    save_csv(out / 'rotulos_detector_faltantes_dev.csv', gaps, ['ID', 'landmark', 'situacao', 'nota'])
    save(out / 'status.json', dict(summary, status='GEOMETRIA_A1_T1_EXECUTADA_PARCIAL',
          bootstrap_unit='conteudo-paciente proxy; mesmos IDs nos quatro métodos por landmark',
          bootstrap_replicates=B, seed=SEED, pontos_disponiveis=len(tables['referencia_A1_T1']),
          pontos_ausentes=len(tables['ausencias']), ICC_calculado=False,
          normalizadores_alterados=False, detector_treinado=False, teste_ML_reaberto=False,
          python=platform.python_version(), numpy=np.__version__,
          congelamento_sha256=sha(HERE / 'congelamento.json')))
    result_hashes = {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}
    save(out / 'manifesto_resultados.json', {'files': result_hashes})
    print(json.dumps(load(out / 'status.json'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--congelar', action='store_true')
    mode.add_argument('--executar', action='store_true')
    args = parser.parse_args()
    if args.check:
        print(json.dumps(audit_annotations()[0], ensure_ascii=False, indent=2))
    elif args.congelar:
        freeze()
    else:
        run()
