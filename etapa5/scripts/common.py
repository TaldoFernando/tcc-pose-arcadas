import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MPLCONFIGDIR']='/private/tmp/goslon-etapa5-mpl'
from pathlib import Path
import sys,csv,json,hashlib,itertools
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import warnings
warnings.filterwarnings('ignore',message='urllib3 v2 only supports OpenSSL.*')
from rigid_icp import *
from anatomical_pair import anatomical_frame,normalize_anatomical
from pca_pair import normalize_pair_points
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'etapa5';SEED=20261105

def load(path):return json.loads((OUT/path).read_text())
def save(path,value):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2))
def csv_save(path,rows):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def csv_read(path):return list(csv.DictReader((OUT/path).open()))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key(p):return p['superior']['sha256']+'|'+p['inferior']['sha256']
def angular(A,B):return min(geodesic_deg(A.T@B@S) for S in SIGNS)
