"""Matemática do complemento visual; não usa Slicer nem marcações reais."""
import sys,unittest,random,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from etapa8_painel_visual import _deslocamentos,_para_canonico,_para_visual
class VisualMathTests(unittest.TestCase):
 def bounds(self,a,b):return [0,10,0,10,a,b]
 def test_overlapping_models_gap_one(self):
  d=_deslocamentos(self.bounds(-1,5),self.bounds(-5,1),1)
  self.assertEqual(d,{'superior':1.5,'inferior':-1.5})
  self.assertEqual((-1+d['superior'])-(1+d['inferior']),1)
 def test_inverted_vertical_order(self):
  d=_deslocamentos(self.bounds(-5,1),self.bounds(-1,5),1)
  self.assertEqual(d,{'superior':-1.5,'inferior':1.5})
 def test_already_separated_not_moved(self):
  self.assertEqual(_deslocamentos(self.bounds(3,6),self.bounds(-3,0),1),{'superior':0.,'inferior':-0.})
 def test_equal_centers_and_empty_invalid_bounds(self):
  d=_deslocamentos(self.bounds(-2,2),self.bounds(-2,2),1)
  self.assertEqual(d['superior'],2.5)
  for b in [self.bounds(5,-5),self.bounds(float('nan'),5)]:
   with self.assertRaises(ValueError):_deslocamentos(b,self.bounds(-1,1),1)
 def test_invalid_gap(self):
  for gap in [0,-1,float('inf'),float('nan')]:
   with self.assertRaises(ValueError):_deslocamentos(self.bounds(-1,2),self.bounds(-2,1),gap)
 def test_roundtrip_zero_and_missing_is_not_fabricated(self):
  p=[0,0,0]
  self.assertEqual(_para_canonico(_para_visual(p,3),3),p)
  self.assertEqual(p,[0,0,0])
  with self.assertRaises((TypeError,ValueError)):_para_canonico(None,3)
 def test_roundtrips_arbitrary_points_and_offsets(self):
  rng=random.Random(20261108)
  for _ in range(200):
   p=[rng.uniform(-100,100) for i in range(3)];dz=rng.uniform(-30,30)
   q=_para_canonico(_para_visual(p,dz),dz)
   for a,b in zip(p,q):self.assertAlmostEqual(a,b,places=12)
 def test_invalid_coordinates(self):
  for p in [[1,2],[1,2,float('nan')],[1,2,float('inf')]]:
   with self.assertRaises(ValueError):_para_visual(p,1)
 def test_frozen_sources_do_not_change(self):
  # Leitura apenas do congelamento já existente; não cria dados clínicos.
  import json,hashlib
  root=Path(__file__).resolve().parents[2]
  lock=root/'etapa8/congelamento.json'
  if not lock.exists():self.skipTest('Entradas privadas indisponíveis no clone público.')
  for name,h in json.loads(lock.read_text())['files'].items():
   self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),h,name)
class TimezoneCompatibilityTests(unittest.TestCase):
 def test_slicer_missing_tzdata_uses_local_TZif(self):
  from unittest.mock import patch,mock_open
  from datetime import timezone,timedelta
  from zoneinfo import ZoneInfoNotFoundError
  import e8_common as common
  common.study_timezone.cache_clear()
  try:
   with patch.object(common,'ZoneInfo',side_effect=ZoneInfoNotFoundError('synthetic')) as zone, patch('pathlib.Path.open',mock_open(read_data=b'TZif synthetic fixture')):
    zone.from_file.return_value=timezone(timedelta(hours=-3))
    self.assertEqual(common.study_timezone().utcoffset(None),timedelta(hours=-3))
    self.assertEqual(zone.from_file.call_args.kwargs['key'],'America/Fortaleza')
  finally:common.study_timezone.cache_clear()
 def test_missing_all_timezone_sources_blocks_export(self):
  from unittest.mock import patch
  from zoneinfo import ZoneInfoNotFoundError
  import e8_common as common
  common.study_timezone.cache_clear()
  try:
   with patch.object(common,'ZoneInfo',side_effect=ZoneInfoNotFoundError('synthetic')),patch('pathlib.Path.open',side_effect=FileNotFoundError('synthetic')):
    with self.assertRaises(ValueError):common.local_today()
  finally:common.study_timezone.cache_clear()
if __name__=='__main__':unittest.main()
