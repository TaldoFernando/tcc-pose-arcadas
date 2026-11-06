"""Flask local: uploads exclusivamente RAM, respostas PNG em memória, sem STL salvo."""
import io,json,re,base64,time,threading
from pathlib import Path
import numpy as np
from flask import Flask,Request,request,jsonify,render_template
from werkzeug.exceptions import RequestEntityTooLarge,BadRequest
from PIL import Image
from pose_normalize import normalize_pair,load_config,verify_frozen,rotation_angle,BASE
from render_views import prepare_mesh,render_views,camera_basis,VIEWS
import model_adapter

class MemoryOnlyRequest(Request):
 def _get_file_stream(self,total_content_length,content_type,filename=None,content_length=None):
  # Evita SpooledTemporaryFile do Werkzeug, inclusive acima de 500 KiB.
  return io.BytesIO()

def parse_stl_bytes(raw,max_triangles=600000):
 if not isinstance(raw,bytes) or len(raw)<15:raise ValueError('STL vazio ou inválido.')
 if len(raw)>=84:
  count=int.from_bytes(raw[80:84],'little')
  if 84+50*count==len(raw):
   if count<1 or count>max_triangles:raise ValueError('Quantidade de triângulos fora do limite.')
   dt=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')]);tri=np.frombuffer(raw,dt,count=count,offset=84)['vertices'].astype(np.float64)
   if not np.isfinite(tri).all():raise ValueError('Coordenadas não finitas no STL.')
   return tri
 try:text=raw.decode('ascii')
 except UnicodeDecodeError:raise ValueError('STL binário truncado ou formato não reconhecido.')
 if not text.lstrip().lower().startswith('solid') or 'endsolid' not in text.lower():raise ValueError('Formato STL ASCII não reconhecido.')
 vertices=[]
 for line in text.splitlines():
  words=line.split()
  if words and words[0].lower()=='vertex':
   if len(words)!=4:raise ValueError('Vértice STL inválido.')
   if len(vertices)>=max_triangles*3:raise ValueError('Malha excede o limite de triângulos.')
   try:vertices.append([float(v) for v in words[1:]])
   except ValueError:raise ValueError('Vértice STL inválido.')
 if not vertices or len(vertices)%3:raise ValueError('Triângulos incompletos no STL.')
 tri=np.asarray(vertices,float).reshape(-1,3,3)
 if not np.isfinite(tri).all():raise ValueError('Coordenadas não finitas no STL.')
 return tri
def frame_metrics(mesh,cfg):
 rows={}
 for view,cam in cfg['views'].items():
  points=np.concatenate([v.reshape(-1,3) for a,v in mesh.items() if cam['mesh']=='ambas' or a==cam['mesh']]);pos,B=camera_basis(cam);q=(points-pos)@B;half=cam['ortho_height']/2;outside=(abs(q[:,0])>half)|(abs(q[:,1])>half)|(q[:,2]<cam['near'])|(q[:,2]>cam['far']);rows[view]={'fraction_vertices_outside':float(outside.mean()),'clipping_detected':bool(outside.any())}
 return rows
def _image_url(array):
 buffer=io.BytesIO();Image.fromarray(array).save(buffer,format='PNG');return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')
def create_app(test_config=None):
 app=Flask(__name__);app.request_class=MemoryOnlyRequest;cfg=load_config();app.config.update(MAX_CONTENT_LENGTH=cfg['limits']['request_bytes'],MAX_FORM_PARTS=8,MAX_FORM_MEMORY_SIZE=500000,TRUSTED_HOSTS=['127.0.0.1','localhost','[::1]']);app.config.update(test_config or {});lock=threading.BoundedSemaphore(1)
 @app.before_request
 def same_origin():
  origin=request.headers.get('Origin')
  if request.method=='POST' and origin and origin.rstrip('/')!=request.host_url.rstrip('/'):return jsonify(error='Origem não autorizada.'),403
 @app.after_request
 def privacy_headers(response):
  response.headers['Cache-Control']='no-store';response.headers['Pragma']='no-cache';response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer';response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'";return response
 @app.errorhandler(RequestEntityTooLarge)
 def too_large(error):return jsonify(error='Par excede 64 MiB ou limites do formulário.'),413
 @app.errorhandler(BadRequest)
 def bad_request(error):return jsonify(error='Formulário inválido.'),400
 @app.get('/')
 def index():return render_template('index.html')
 @app.get('/api/config')
 def config():
  camera=json.loads((BASE/'camera_config.json').read_text());return jsonify(config=cfg,cameras=camera)
 @app.get('/api/health')
 def health():
  verify_frozen();return jsonify(status='ok',STL_storage='RAM_ONLY',original_training_cameras='PLACEHOLDER',classifier='stub',normalization='multi5_rmse_frozen')
 def inputs():
  if set(request.files)!={'superior','inferior'} or any(len(request.files.getlist(a))!=1 for a in ['superior','inferior']):raise ValueError('Envie exatamente um STL superior e um inferior.')
  identifier=request.form.get('ID','P000')
  if not re.fullmatch(r'P\d{3}',identifier):raise ValueError('ID inválido; use P001…P999, ou P000 temporário.')
  meshes={}
  for a in ['superior','inferior']:
   upload=request.files[a]
   if not isinstance(upload.stream,io.BytesIO):raise RuntimeError('Upload não está em memória.')
   raw=upload.stream.read(cfg['limits']['file_bytes']+1)
   if len(raw)>cfg['limits']['file_bytes']:raise ValueError('Cada STL deve ter no máximo 30 MiB.')
   meshes[a]=parse_stl_bytes(raw,cfg['limits']['triangles_per_arch'])
  return identifier,meshes
 @app.post('/api/process')
 def process():
  if not lock.acquire(blocking=False):return jsonify(error='Processamento local ocupado. Tente novamente.'),429
  try:
   start=time.perf_counter();identifier,meshes=inputs();normalized,alignment=normalize_pair(meshes['superior'],meshes['inferior']);camera=json.loads((BASE/'camera_config.json').read_text());frames=frame_metrics(normalized,camera);clipped=any(v['clipping_detected'] for v in frames.values());alignment['flags'].append({'code':'view_framing','level':'attention' if clipped else 'ok','message':'Enquadramento nas câmeras próprias fixas; não certifica equivalência ao treino original.','value':frames,'advisory':True});alignment['uncertain']=alignment['uncertain'] or clipped
   images=render_views(prepare_mesh(normalized,camera['appearance']['shading']),camera);prediction=model_adapter.predict(images,'OWN_CANONICAL_224_ORTHOGRAPHIC');payload={'ID':identifier,'class':prediction['class'],'prediction':prediction,'views':{v:_image_url(images[v]) for v in VIEWS},'alignment':alignment,'cameras_original_training':'PLACEHOLDER','reference_kind':cfg['reference']['kind'],'seconds':time.perf_counter()-start,'privacy':{'STL_saved':False,'upload_storage':'RAM_ONLY','external_processing':False},'notice':'Consistência geométrica não certifica correção anatômica; apoio à revisão clínica.'};return jsonify(payload)
  except ValueError as e:return jsonify(error=str(e)),400
  except RuntimeError:return jsonify(error='Configuração congelada ou transformação inválida. Verifique a instalação local.'),503
  finally:lock.release()
 @app.post('/api/robustness')
 def robustness():
  if not lock.acquire(blocking=False):return jsonify(error='Processamento local ocupado.'),429
  try:
   from scipy.spatial.transform import Rotation
   identifier,meshes=inputs()
   try:n=int(request.form.get('N','3'))
   except ValueError:raise ValueError('N deve ser inteiro.')
   if not 1<=n<=cfg['limits']['robustness_N_max']:raise ValueError('Use N entre 1 e 5.')
   _,baseline=normalize_pair(meshes['superior'],meshes['inferior']);R0=np.array(baseline['R']);rng=np.random.default_rng(20261109);errors=[]
   for j in range(n):
    Q=Rotation.random(random_state=rng).as_matrix();shift=rng.uniform(-100,100,3);_,fit=normalize_pair(meshes['superior']@Q.T+shift,meshes['inferior']@Q.T+shift);errors.append(rotation_angle(np.array(fit['R'])@Q@R0.T))
   return jsonify(ID=identifier,N=n,errors_deg=errors,mean_deg=float(np.mean(errors)),std_deg=float(np.std(errors)),max_deg=float(np.max(errors)),kind='EQUIVARIANCIA_NUMERICA_ROTACOES_PURAS',realistic_robustness_claim=False,STL_saved=False)
  except ValueError as e:return jsonify(error=str(e)),400
  except RuntimeError:return jsonify(error='Dependência congelada inválida.'),503
  finally:lock.release()
 return app
if __name__=='__main__':create_app().run(host='127.0.0.1',port=8765,debug=False,use_reloader=False,threaded=True)
