"""Novas 51 condições centralizadas; backbone estritamente local e sem ICP."""
import os
for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:os.environ[k]="1"
from pathlib import Path
import sys,json,time,hashlib,argparse,concurrent.futures
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[3];OLD=ROOT/"etapa7b";OUT=OLD/"correcoes_v2"
sys.path[:0]=[str(OLD),str(ROOT/"etapa6"),str(ROOT/"etapa5")]
from experimento import moved,rotation,angle,descriptors
from render_views import read_stl,prepare_mesh,render_views,VIEWS
from rigid_icp import sample_surface
from centralizar import center_pair

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify():
 freeze=load(OUT/"congelamento.json")
 for name,digest in freeze["files"].items():
  if sha(ROOT/name)!=digest:raise RuntimeError("Entrada congelada alterada: "+name)

def worker(identifier):
 import torch
 from torchvision.models import mobilenet_v3_small
 start=time.monotonic();target=OUT/"features"/f"{identifier}.npz"
 if target.exists():return {"ID":identifier,"cache":True}
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(20261106)
 whole=mobilenet_v3_small(weights=None);whole.load_state_dict(torch.load(OLD/"backbone/mobilenet_v3_small-047dcff4.pth",map_location="cpu",weights_only=True));net=whole.features.eval();net.requires_grad_(False)
 mean=torch.tensor([.485,.456,.406])[None,:,None,None];std=torch.tensor([.229,.224,.225])[None,:,None,None]
 cfg=load(OLD/"camera_config_proprio.json");assert all(np.allclose(cam["target"],0) for cam in cfg["views"].values())
 pair={p["id"]:p for p in load(ROOT/"etapa5/pares_ids.json")}[identifier]
 original=prepare_mesh({a:read_stl(ROOT/"etapa5"/pair[a]["arquivo"]) for a in ["superior","inferior"]})
 tr0={r["ID"]:r for r in load(ROOT/"etapa6/stl/transformacoes.json")}[identifier];R0=np.array(tr0["R"]);t0=np.array(tr0["t"]);base=moved(original,R0,t0)
 clouds=np.load(ROOT/"etapa5/clouds"/f"{identifier}.npz");u=clouds["superior_base"];l=clouds["inferior_base"];center=((u@R0.T+t0).mean(0)+(l@R0.T+t0).mean(0))/2
 records=[];features=[];desc=[];hashes=[];pending=[];meta=[];renderseconds=0.
 def flush():
  if not pending:return
  images=np.stack(pending).reshape(-1,224,224,3);x=torch.from_numpy(images.copy()).permute(0,3,1,2).float()/255
  with torch.inference_mode():f=net((x-mean)/std).mean((2,3)).reshape(len(pending),6,576).numpy()
  for j,(r,im,hh) in enumerate(meta):records.append(r);features.append(f[j]);desc.append(descriptors(im));hashes.append(hh)
  pending.clear();meta.clear()
 def emit(mesh,condition,axis="nenhum",deg=0.,sign=0,trial=-1,pose_error=0.):
  nonlocal renderseconds
  centered,R,t=center_pair(mesh);assert np.array_equal(R,np.eye(3))
  s=time.monotonic();ims=render_views(centered,cfg);im=np.stack([ims[v] for v in VIEWS]);renderseconds+=time.monotonic()-s
  empty=sum(np.max(abs(x.astype(float)-32))<=5 for x in im)
  borders=sum(bool((np.max(abs(np.concatenate([x[0],x[-1],x[:,0],x[:,-1]]).astype(float)-32),axis=1)>5).any()) for x in im)
  r={"ID":identifier,"condition":condition,"method":"centralizado","axis":axis,"angle":deg,"sign":sign,"trial":trial,"pose_error_deg":pose_error,"rmse":0.,"template_ID":"","augmentation":0,"empty_views":int(empty),"border_views":int(borders),"centering_translation":t.tolist(),"centering_R_identity":True}
  pending.append(im);meta.append((r,im,hashlib.sha256(im.tobytes()).hexdigest()))
  if len(pending)==8:flush()
 emit(base,"canonical")
 for ax in ["vertical","anteroposterior","lateral"]:
  for deg in [2,3,5,10,20]:
   for sign in [-1,1]:
    q=rotation(ax,sign*deg);emit(moved(base,q,center-q@center),"rotation",ax,deg,sign,pose_error=deg)
 for trial in range(20):
  key=f"{trial:02d}";Q=clouds[f"Q{key}"];tr=clouds[f"t{key}"]
  rng=np.random.default_rng(20261105+1000*int(identifier[1:])+trial);checkQ=Rotation.random(random_state=rng).as_matrix();checkt=rng.uniform(-100,100,3)
  assert np.allclose(Q,checkQ) and np.allclose(tr,checkt)
  tri={}
  for a in ["superior","inferior"]:
   level=str(rng.choice(["leve","forte"]));tri[a]=np.load(ROOT/"etapa5/cache"/identifier/f"{a}_{level}.npz")["tri"]
   seed=int(rng.integers(1,2**31));pts=sample_surface(tri[a],2048,seed);rng.normal(0,.15,pts.shape);rng.uniform(.10,.30);rng.integers(len(pts))
  emit(moved(prepare_mesh(tri),R0@Q,R0@tr+t0),"realistic",trial=trial,pose_error=angle(R0@Q@R0.T))
 flush();assert len(records)==51
 temp=target.with_suffix(".partial.npz");np.savez_compressed(temp,features=np.array(features,np.float32),descriptors=np.array(desc,np.float32),records=np.array(json.dumps(records)),pixel_hashes=np.array(hashes));temp.replace(target)
 timing={"ID":identifier,"conditions":51,"render_seconds":renderseconds,"total_seconds":time.monotonic()-start};target.with_suffix(".json").write_text(json.dumps(timing,indent=2));return timing
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--workers",type=int,default=6);ap.add_argument("--ids",nargs="*");a=ap.parse_args();verify();ids=a.ids or [u["ID"] for u in load(OLD/"unidades.json")]
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
  for result in pool.map(worker,ids):print(json.dumps(result),flush=True)
