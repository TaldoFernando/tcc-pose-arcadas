"""Abre P016 sem colocar pontos em processo separado; confere o congelamento real."""
from pathlib import Path
import datetime,json,os,sys,traceback
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import slicer
import e8_common as common
import slicer_markups as e8
import etapa8_painel_visual as visual
OUT=ROOT/"qa/consolidacao_protocolo_20261110"
try:
 assert e8._SESSION is None,"Não executar na sessão humana."
 assert not list((ROOT/"template").glob("*.json")),"Template real já existe; preservar a coleta."
 before={p:common.sha(p) for folder in ["piloto_marcacoes","referencias_piloto"] for p in (ROOT/folder).glob("*") if p.is_file()}
 slicer.util.mainWindow().hide();visual.abrir_template();s=e8._SESSION
 assert s["ID"]=="P016" and len(s["definitions"])==18 and s["marks"].GetNumberOfDefinedControlPoints()==0
 assert s["protocol_file"]=="landmarks_validados_v2.json" and s["proposals"]=={}
 assert len(visual._aberto.combos)==18 and visual._aberto.referencias_widgets=={}
 visual.fechar();s["dialog"].close()
 assert not list((ROOT/"template").glob("*.json"))
 assert all(common.sha(p)==value for p,value in before.items())
 result={"status":"PASS","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"Slicer":slicer.app.applicationVersion,"helper_abrir_template_verificado":True,"P016_aberto_com_18_pontos_indefinidos":True,"protocolo_congelado_verificado":True,"nenhum_template_humano_gravado":True,"pilotos_preservados":True,"sessao_real_acessada":False};code=0
except Exception:
 result={"status":"FAIL","traceback":traceback.format_exc()};code=1
(OUT/"abertura_template_real_sem_marcar.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n");print(json.dumps(result,ensure_ascii=False,indent=2))
if os.environ.get("ETAPA8_ABERTURA_BATCH")=="1":slicer.util.exit(code)
elif code:raise RuntimeError(result["traceback"])
