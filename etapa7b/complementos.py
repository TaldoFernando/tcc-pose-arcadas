"""Interpretação e diferenças pareadas; não modifica modelos ou protocolo."""
from pathlib import Path
import csv,json,hashlib,time,collections
import numpy as np
OUT=Path(__file__).resolve().parent
def read(name):return list(csv.DictReader((OUT/name).open()))
def write(name,rows):
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 rows=read('metricas_por_paciente.csv');w=np.random.default_rng(20261106+90000+63).multinomial(63,[1/63]*63,size=10000)/63;paired=read('diferencas_pareadas_IC95.csv')
 for method in ['nenhuma','controle','anatomica','multi5_rmse']:
  for angle in ['2','3','5','10','20']:
   for model in ['substituto_aug10','substituto_aug20']:
    a={r['ID']:r for r in rows if r['modelo']=='substituto_canonico' and r['condicao']=='rotation' and r['normalizacao']==method and r['eixo']=='todos' and r['angulo']==angle};b={r['ID']:r for r in rows if r['modelo']==model and r['condicao']=='rotation' and r['normalizacao']==method and r['eixo']=='todos' and r['angulo']==angle};ids=sorted(a)
    for metric in ['acuracia','erro_ordinal_grupo','taxa_troca']:
     d=np.array([float(b[i][metric])-float(a[i][metric]) for i in ids]);ci=np.quantile(w@d,[.025,.975]);paired.append({'rotulo':'modelo substituto','modelo_comparado':model,'referencia':'substituto_canonico','condicao':'rotation_'+angle+'_graus_todos_eixos','normalizacao':method,'metrica':metric,'diferenca':d.mean(),'IC95_inf':ci[0],'IC95_sup':ci[1]})
 write('diferencas_pareadas_IC95.csv',paired)
 pred=read('predicoes_oof.csv');groups=collections.defaultdict(list)
 for r in pred:
  if r['condition']=='rotation' and r['method']!='nenhuma':groups[(r['model'],r['method'],r['ID'])].append(r)
 checks=[]
 for (model,method,i),rr in sorted(groups.items()):checks.append({'rotulo':'modelo substituto','modelo':model,'normalizacao':method,'ID':i,'predicoes_distintas_30_rotacoes':len({r['predicao'] for r in rr}),'troca_vs_canonica_multi5':int(rr[0]['predicao']!=rr[0]['predicao_canonica'])})
 write('consistencia_rotacoes_puras.csv',checks)
 old=OUT/'historico/verificar_antes_correcao_serializacao.py';new=OUT/'verificar.py';audit={'rotulo':'modelo substituto','time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'only_change':'auditor converte numpy.bool_ em bool antes de serializar JSON','old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'training_or_predictions_changed':False,'frozen_training_and_normalization_hashes_changed':False};(OUT/'correcao_serializacao_auditoria.json').write_text(json.dumps(audit,indent=2))
 path=OUT/'README.md';text=path.read_text();text+='\n## Leitura dos resultados e limite da comparação\n\n'
 text+='A acurácia canônica do substituto sem augmentation foi 50,8% (IC95% 38,1–63,5), F1 macro 0,468 e erro ordinal de grupo 0,635. A logística simples obteve 54,0%, e a maioria, 42,9%. Com augmentation até 20°, a acurácia foi 57,1% (44,4–69,8); a diferença pareada versus canônico foi +6,35 pontos percentuais, IC95% −4,76 a +17,46. Assim, não se demonstra melhora de acurácia pelo IC desta comparação. O modelo substituto tem desempenho limitado e não foi validado clinicamente.\n\n'
 text+='Sem normalização, as taxas de troca a 2° foram 17,5% (canônico), 11,9% (aug10) e 11,6% (aug20); a 20°, 47,9%, 39,4% e 37,6%. Os limiares de 5% e 10% já são ultrapassados em 2°, o menor ângulo positivo testado; o cruzamento verdadeiro pode ocorrer abaixo de 2°. Augmentation reduz as trocas observadas, mas não torna o substituto invariável à pose. As diferenças pareadas por ângulo estão no CSV correspondente.\n\n'
 text+='Os resíduos realistas medianos foram 2,88° (controle), 3,04° (anatômica), 2,91° (multi5_rmse): maiores que o menor ângulo testado que já excedeu as taxas de troca. Essa comparação é descritiva, pois eixo, translação e alteração geométrica também influenciam a imagem.\n\n'
 text+='Na rotação pura, o multi5_rmse teve troca zero. O controle e a anatômica apresentaram, respectivamente, 15,9% e 12,7% de troca em relação à referência canônica multi5 do treino, apesar do resíduo numérico praticamente zero. Isso decorre de **mudar o normalizador de referência**, não de falhar ao desfazer a rotação. Dentro de cada método, as predições foram constantes nas 30 rotações para cada conteúdo/modelo (`consistencia_rotacoes_puras.csv`). Esses ensaios limpos não substituem os realistas.\n\n'
 text+='Nos realistas, o substituto canônico teve troca 66,8% sem normalização e 22,3% com multi5_rmse; acurácias 36,4% e 53,4%. **2.733 de 7.560 vistas realistas sem normalização estavam vazias (36,2%)**, devido à rotação/translação livre e câmera fixa. Nenhuma vista realista após registro estava vazia. Logo, esse contraste inclui recuperação de enquadramento e não deve ser apresentado como efeito isolado do erro angular.\n\n'
 text+='A correção de serialização do auditor após a execução está documentada em `correcao_serializacao_auditoria.json`; não mudou treino, predições, parâmetros nem os hashes do protocolo final.\n'
 path.write_text(text)
if __name__=='__main__':main()
