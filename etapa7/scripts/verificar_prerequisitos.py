from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'etapa7'
def main():
 cfg=json.loads((OUT/'modelo_config.json').read_text());missing=[]
 for field in ['model_file','format','model_input_structure','view_order','class_values_in_output_order','target_semantics','resize_and_crop','RGB_channel_normalization']:
  if cfg.get(field) is None:missing.append(field)
 path=Path(cfg['model_file']) if cfg.get('model_file') else None
 if path is not None and not path.is_file():missing.append('model_file_not_found')
 if not missing:missing.append('model_adapter_and_output_semantics_must_be_verified_before_evaluation')
 frozen=json.loads((OUT/'entradas_congeladas.json').read_text());changed=[p for p,h in frozen['hashes'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
 result={'status':'PENDING_TRAINED_CLASSIFIER','missing_model_metadata':missing,'frozen_input_mismatches':changed,'evaluation_executed':False};(OUT/'resultados/prerequisitos.json').write_text(json.dumps(result,indent=2));print('ETAPA 7 PENDENTE: faltam modelo treinado e metadados de inferência. Nenhuma avaliação foi executada.');return 2
if __name__=='__main__':sys.exit(main())
