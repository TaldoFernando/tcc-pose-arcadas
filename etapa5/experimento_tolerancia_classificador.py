"""PREPARADO, NÃO EXECUTADO. Adaptadores devem ser locais; nenhuma chamada de rede.

Rotações de 0,2,3,5,10,20 graus em cada eixo separadamente. Nenhum resultado
é fabricado enquanto câmeras e classificador não estiverem disponíveis.
"""
from pathlib import Path
import csv,json,re,copy
import numpy as np
from scipy.spatial.transform import Rotation

ANGLES=(0,2,3,5,10,20)
AXES=('lateral','AP','vertical')
VIEW_NAMES=('Angulada','Direita','Esquerda','Up','Frontal','Inferior')

def render_views(mesh,camera):
    """STUB: retornar dict das seis imagens, com câmeras de treino verificadas."""
    raise NotImplementedError('Conectar renderizador LOCAL; câmeras ainda PLACEHOLDER.')

def predict(images):
    """STUB: retornar {'classe': int, 'probabilidades': list[float]} localmente."""
    raise NotImplementedError('Conectar classificador LOCAL; modelo não fornecido.')

def rotated_copy(mesh,axis_vector,angle_deg):
    """mesh={'superior':triângulos Nx3x3,'inferior':...}; mesmo R nas duas."""
    out=copy.deepcopy(mesh);points=np.concatenate([np.asarray(mesh[k]).reshape(-1,3) for k in ('superior','inferior')]);center=points.mean(0)
    axis=np.asarray(axis_vector,float);axis/=np.linalg.norm(axis);R=Rotation.from_rotvec(np.deg2rad(angle_deg)*axis).as_matrix()
    for k in ('superior','inferior'):out[k]=(np.asarray(mesh[k])-center)@R.T+center
    return out

def contains_placeholder(value):
    if isinstance(value,dict):return any(contains_placeholder(v) for v in value.values())
    if isinstance(value,(list,tuple)):return any(contains_placeholder(v) for v in value)
    return isinstance(value,str) and 'PLACEHOLDER' in value.upper()

def run_experiment(pairs,camera,normalizer,canonical_frame,output_csv,*,adapters_confirmed=False,signs=(1,)):
    """Chamar explicitamente só depois de plugar adapters. Não é executado neste projeto.

    normalizer recebe a cópia do par e devolve o par transformado por UM R/t.
    As predições são comparadas tanto com referência própria de cada ramo
    quanto com referência original comum; consistência de predição não é acurácia.
    """
    if not adapters_confirmed or contains_placeholder(camera):raise RuntimeError('Execução bloqueada: adapters/câmeras ainda não confirmados.')
    F=np.asarray(canonical_frame,float)
    if F.shape!=(3,3) or not np.allclose(F.T@F,np.eye(3)) or np.linalg.det(F)<0:raise ValueError('Frame canônico próprio obrigatório.')
    rows=[]
    for identifier,mesh in pairs:
        if not re.fullmatch(r'P\d{3}',identifier):raise ValueError('Usar somente IDs P001...')
        ref_direct=predict(render_views(copy.deepcopy(mesh),camera));ref_norm=predict(render_views(normalizer(copy.deepcopy(mesh)),camera))
        for j,axis in enumerate(AXES):
            for angle in ANGLES:
                for sign in ((1,) if angle==0 else signs):
                    rotated=rotated_copy(mesh,F[:,j],sign*angle)
                    direct=predict(render_views(copy.deepcopy(rotated),camera));normalized=predict(render_views(normalizer(copy.deepcopy(rotated)),camera))
                    rows.append({'ID':identifier,'eixo':axis,'graus':sign*angle,'pred_sem_normalizacao':int(direct['classe']),'pred_com_normalizacao':int(normalized['classe']),'referencia_original':int(ref_direct['classe']),'referencia_normalizada':int(ref_norm['classe']),'mudou_sem_normalizar':int(direct['classe'])!=int(ref_direct['classe']),'mudou_com_normalizar_ref_propria':int(normalized['classe'])!=int(ref_norm['classe']),'com_normalizacao_vs_ref_original':int(normalized['classe'])!=int(ref_direct['classe']),'probabilidades_sem':json.dumps(direct.get('probabilidades')),'probabilidades_com':json.dumps(normalized.get('probabilidades'))})
    with Path(output_csv).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    return rows

if __name__=='__main__':
    raise SystemExit('SCRIPT PREPARADO, EXPERIMENTO NÃO EXECUTADO. Plugar render_views/predict e câmeras verificadas antes da chamada explícita.')
