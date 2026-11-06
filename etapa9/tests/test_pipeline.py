"""Testes reais locais; nenhuma cópia de upload é salva pelo endpoint."""
import io,json,csv,hashlib,sys,base64
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parent;sys.path.insert(0,str(BASE))
from app import create_app,parse_stl_bytes,MemoryOnlyRequest
from pose_normalize import normalize_pair
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def assert_original_unchanged(path,expected):
 if digest(path)!=expected:raise AssertionError('STL original modificado durante o processamento.')
@pytest.fixture(scope='module')
def original_pair():
 p=next(p for p in json.loads((ROOT/'etapa5/pares_ids.json').read_text()) if p['id']=='P001')
 with (ROOT/'inventario.csv').open() as f:inventory=list(csv.DictReader(f))
 result={}
 for a in ['superior','inferior']:
  row=next(r for r in inventory if r['sha256']==p[a]['sha256']);path=ROOT/'dados'/row['arquivo'];assert path.is_file();raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256'];result[a]={'path':path,'raw':raw,'sha256':row['sha256'],'tri':parse_stl_bytes(raw)}
 yield result
 for item in result.values():assert_original_unchanged(item['path'],item['sha256'])
@pytest.fixture(scope='module')
def normalized(original_pair):
 u=original_pair['superior']['tri'];l=original_pair['inferior']['tri'];u.flags.writeable=False;l.flags.writeable=False;return normalize_pair(u,l)
def test_rotation_SO3_det_positive_and_same_transform_for_pair(original_pair,normalized):
 meshes,fit=normalized;R=np.array(fit['R']);t=np.array(fit['t']);assert np.allclose(R.T@R,np.eye(3),atol=1e-8);assert np.isclose(np.linalg.det(R),1.,atol=1e-8)
 for a in ['superior','inferior']:assert np.allclose(meshes[a],original_pair[a]['tri']@R.T+t);assert np.array_equal(original_pair[a]['tri'],parse_stl_bytes(original_pair[a]['raw']))
def test_exact_frozen_variant_not_reselected_from_labels(normalized):
 _,fit=normalized;old=next(r for r in json.loads((ROOT/'etapa6/stl/transformacoes.json').read_text()) if r['ID']=='P001');assert np.allclose(fit['R'],old['R'],atol=1e-9);assert np.allclose(fit['t'],old['t'],atol=1e-9);assert np.isclose(fit['RMSE'],old['RMSE'],atol=1e-9);assert fit['template_ID']==old['template_ID']
def test_warning_is_advisory_not_old_gate(monkeypatch,original_pair,normalized):
 import pose_normalize
 cfg=pose_normalize.load_config();cfg['quality']['rmse_warn_mm']=0.;monkeypatch.setattr(pose_normalize,'load_config',lambda:cfg);_,fit=normalize_pair(original_pair['superior']['tri'],original_pair['inferior']['tri']);assert fit['uncertain'];assert any(f['code']=='registration_rmse' and f['level']=='attention' for f in fit['flags']);assert np.allclose(fit['R'],normalized[1]['R'])
def test_upload_factory_never_spools_to_disk():
 req=MemoryOnlyRequest.from_values('/');stream=req._get_file_stream(20_000_000,'model/stl','ignored.stl',20_000_000);assert type(stream) is io.BytesIO
def test_pair_to_six_images_memory_only_and_original_hashes(monkeypatch,original_pair,tmp_path):
 import werkzeug.formparser,werkzeug.datastructures
 def forbidden(*a,**k):raise AssertionError('Não deve criar spool em disco nem salvar upload.')
 monkeypatch.setattr(werkzeug.formparser,'SpooledTemporaryFile',forbidden);monkeypatch.setattr(werkzeug.datastructures.FileStorage,'save',forbidden)
 app=create_app({'TESTING':True});client=app.test_client();before=set(BASE.rglob('*.stl'))
 # Cada arquivo real excede 500 KiB, que acionaria o comportamento padrão.
 assert all(len(original_pair[a]['raw'])>512*1024 for a in ['superior','inferior'])
 result=client.post('/api/process',data={'ID':'P001',**{a:(io.BytesIO(original_pair[a]['raw']),a+'.stl') for a in ['superior','inferior']}},content_type='multipart/form-data');assert result.status_code==200;obj=result.get_json();assert obj['ID']=='P001';assert obj['class'] is None;assert obj['prediction']['mode']=='stub';assert obj['privacy']['STL_saved'] is False;assert obj['privacy']['upload_storage']=='RAM_ONLY';assert result.headers['Cache-Control']=='no-store';assert set(obj['views'])=={'Angulada','Direita','Esquerda','Up','Frontal','Inferior'}
 for name,url in obj['views'].items():
  image=Image.open(io.BytesIO(base64.b64decode(url.split(',',1)[1])));assert image.format=='PNG';assert image.size==(224,224);assert np.max(abs(np.asarray(image).astype(int)-32))>5
 assert set(BASE.rglob('*.stl'))==before
 for item in original_pair.values():assert_original_unchanged(item['path'],item['sha256'])
def test_original_guard_detects_tampering_in_disposable_synthetic_file(tmp_path):
 path=tmp_path/'original_sintetico.stl';path.write_bytes(b'SYNTHETIC_NO_PATIENT_DATA');expected=digest(path);path.write_bytes(b'SYNTHETIC_MODIFIED')
 with pytest.raises(AssertionError,match='original modificado'):assert_original_unchanged(path,expected)
@pytest.mark.parametrize('raw',[b'',b'not an stl',b'solid x\nvertex nan 0 1\nvertex 0 0 0\nvertex 1 1 1\nendsolid x'])
def test_invalid_STL_rejected(raw):
 with pytest.raises(ValueError):parse_stl_bytes(raw)
def test_ascii_parser_and_immutable_input():
 raw=b'solid x\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid x';assert parse_stl_bytes(raw).shape==(1,3,3)
def test_form_validation_and_cross_origin():
 client=create_app({'TESTING':True}).test_client();assert client.post('/api/process',data={}).status_code==400;assert client.post('/api/process',data={},headers={'Origin':'https://example.invalid'}).status_code==403
def test_request_size_limit():
 client=create_app({'TESTING':True,'MAX_CONTENT_LENGTH':100}).test_client();r=client.post('/api/process',data={'superior':(io.BytesIO(b'x'*1000),'superior.stl'),'inferior':(io.BytesIO(b'x'*1000),'inferior.stl')});assert r.status_code==413
def test_health_and_offline_assets():
 client=create_app({'TESTING':True}).test_client();assert client.get('/api/health').get_json()['classifier']=='stub';assert client.get('/').status_code==200
 for name in ['three.module.js','OrbitControls.js','STLLoader.js']:assert client.get('/static/vendor/'+name).status_code==200
