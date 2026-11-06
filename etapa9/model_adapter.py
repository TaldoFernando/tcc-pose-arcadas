"""Contrato de inferência. Não inventa classe na ausência do classificador."""
def predict(images,camera_profile):
 required={'Angulada','Direita','Esquerda','Up','Frontal','Inferior'}
 if set(images)!=required:raise ValueError('O modelo exige as seis vistas nomeadas.')
 return {'mode':'stub','class':None,'probabilities':None,'class_semantics':'PLACEHOLDER','model_loaded':False,'Goslon_AI':False,'substitute_7B_loaded':False,'message':'Classificador não disponível. Nenhuma classe GOSLON ou grupo foi estimado.','camera_profile':camera_profile}
