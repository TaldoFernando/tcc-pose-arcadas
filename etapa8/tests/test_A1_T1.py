"""Execução de avaliador único: somente fixtures sintéticas temporárias."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from fixtures import SyntheticStudy
from e8_common import load

spec = importlib.util.spec_from_file_location('e8_A1T1', HERE.parent / 'a1t1_v4/executar.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)


class SingleRaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e8-A1T1-SOMENTE-SINTETICO-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.f = SyntheticStudy(self.root)
        for i in self.f.ids[:21]:
            self.f.write(self.f.annotation(i))

    def test_partial_A1_T1_runs_without_A2_T2_or_ICC(self):
        summary, found, paths, definitions, transforms, groups = single.audit_annotations(self.root)
        self.assertEqual(summary['principais_validos'], 21)
        self.assertEqual(summary['IDs_faltantes_plano_original'], self.f.ids[21:])
        self.assertTrue(summary['analise_parcial'])
        self.assertTrue(summary['ready_geometria'])
        self.assertEqual(summary['confiabilidade'], 'nao_avaliada')
        self.assertFalse(summary['A2_exigido'] or summary['T2_exigido'] or summary['ICC_exigido'])
        tables = single.geometric_tables(found, definitions, transforms, groups, b=100)
        self.assertEqual(len(tables['por_ID']), 21)
        # Identical identity transforms give exactly zero paired differences.
        self.assertTrue(all(r['delta_desvio_mm'] in [None, 0.] for r in tables['contrastes_pareados']))

    def test_duplicate_export_fails(self):
        self.f.write(self.f.annotation(), name='duplicada.json')
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            single.audit_annotations(self.root)

    def test_invalid_coordinate_fails(self):
        obj = self.f.annotation()
        obj['points'][0]['position'] = [1., 2.]
        self.f.write(obj)
        with self.assertRaisesRegex(ValueError, 'Coordenada'):
            single.audit_annotations(self.root)

    def test_changed_frozen_STL_fails(self):
        asset = self.root / 'modelo.stl'
        asset.write_bytes(b'fixture')
        from e8_common import sha
        self.f.save('congelamento.json', {'files': {str(asset.relative_to(self.root.parent)): sha(asset)}})
        asset.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'congelada alterada'):
            single.audit_annotations(self.root)

    def test_missing_points_are_reported_without_imputation(self):
        for i in self.f.ids[:21]:
            obj = self.f.annotation(i)
            obj['points'][0].update(position=None, status='nao_visivel')
            self.f.write(obj)
        _, found, _, definitions, transforms, groups = single.audit_annotations(self.root)
        tables = single.geometric_tables(found, definitions, transforms, groups, b=50)
        self.assertEqual(len(tables['ausencias']), 21)
        rows = [r for r in tables['dispersao'] if r['landmark'] == 'U1_R']
        self.assertTrue(all(r['n_conteudos'] == 0 and r['desvio_espacial_mm'] is None for r in rows))

    def test_rotation_change_preserves_pairwise_distances(self):
        transforms = self.f.transforms['IDs']
        rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        matrix = np.eye(4)
        matrix[:3, :3], matrix[:3, 3] = rotation, [7., 8., 9.]
        i = self.f.ids[0]
        transforms[i]['methods']['controle'] = matrix.tolist()
        from e8_common import convert_point
        a, b = [1., 2., 3.], [4., 5., 9.]
        self.assertAlmostEqual(np.linalg.norm(convert_point(a, i, 'controle', transforms) -
                                             convert_point(b, i, 'controle', transforms)), np.linalg.norm(np.array(a) - b))

    def test_content_patient_and_alias_leakage_fail(self):
        eligible = [{'ID': 'P901', 'aliases': ['P901', 'P903'], 'conteudo_hash': 'a', 'bloco_paciente_proxy': 'P901'},
                    {'ID': 'P902', 'aliases': ['P902'], 'conteudo_hash': 'b', 'bloco_paciente_proxy': 'P902'}]
        split = {'dev_IDs': ['P901'], 'test_IDs': ['P902']}
        single.audit_partition(eligible, split, [])
        eligible[1]['aliases'].append('P903')
        with self.assertRaisesRegex(ValueError, 'Alias'):
            single.audit_partition(eligible, split, [])
        eligible[1]['aliases'].pop()
        eligible[1]['conteudo_hash'] = 'a'
        with self.assertRaisesRegex(ValueError, 'idêntico'):
            single.audit_partition(eligible, split, [])
        eligible[1]['conteudo_hash'] = 'b'
        eligible[1]['bloco_paciente_proxy'] = 'P901'
        with self.assertRaisesRegex(ValueError, 'cruza'):
            single.audit_partition(eligible, split, [])


if __name__ == '__main__':
    unittest.main()
