from pathlib import Path
import csv,json,collections
root=Path(__file__).resolve().parents[1]
c=json.loads((root/'config.json').read_text()); rows=list(csv.DictReader((root/'inventario.csv').open()))
groups=collections.defaultdict(list); hashes=collections.defaultdict(list)
for r in rows: groups[(r['grupo'],r['pasta_paciente'])].append(r);hashes[r['sha256']].append(r)
dups=[{'sha256':h,'arquivos':[r['arquivo'] for r in rs]} for h,rs in hashes.items() if len(rs)>1]
(root/'relatorios/duplicatas.json').write_text(json.dumps(dups,ensure_ascii=False,indent=2))
with (root/'relatorios/pacientes.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['grupo','pasta_paciente','stl','superior','inferior','registro_mordida','indeterminada'])
 for (g,p),rs in sorted(groups.items()): w.writerow([g,p,len(rs),*[sum(r['arcada']==a for r in rs) for a in ['superior','inferior','registro_mordida','indeterminada']]])
with (root/'relatorios/estrutura.txt').open('w') as f:
 for p in sorted((root/'dados').rglob('*')):
  f.write('  '*(len(p.relative_to(root/'dados').parts)-1)+p.name+('/' if p.is_dir() else '')+'\n')
stats=c['pca']['dispersao_graus']; table='\n'.join(f"| {a} | {s['pares']} | {s['min']:.2f} | {s['mediana']:.2f} | {s['max']:.2f} |" for a,s in stats.items())
wide=max(s['max'] for s in stats.values());c['pca']['conclusao']='Dispersão heterogênea: normalização e validação necessárias; não assumir pose de treino.' if wide>10 else 'Pose geométrica semelhante; orientação anatômica ainda exige validação.'
c['duplicatas_grupos_sha256']=len(dups);c['rar_internos']=3
(root/'config.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
text=f'''# Goslon AI — inspeção dos dados reais (Passo 0)

ZIP extraído em `dados/`, incluindo os três RAR internos. Nenhum upload foi realizado. O repositório estava vazio, exceto por `.git`; não foram encontrados scripts de geração das seis vistas no ZIP ou nos RAR.

## Estrutura e agrupamento

- {c['stl']} STL físicos, {c['stl_unicos_sha256']} conteúdos únicos por SHA-256, {c['pastas_paciente_com_stl']} pastas com STL.
- Arcadas por nome: {c['arcadas']}.
- `MaxillaryAnatomy` / `UpperJaw`: superior; `MandibularAnatomy` / `LowerJaw`: inferior; `BiteAverage`: registro de mordida (não uma arcada).
- Há prefixos de nome, UUID `3DIO_00` e nomes numéricos sem indicação de arcada. Estes ficam indeterminados, sem inferência pela geometria.
- As arcadas estão separadas em arquivos; não existe regra uniforme de exatamente dois STL por pasta. Pastas com nomes semelhantes ou idades distintas podem repetir conteúdo. Pastas não equivalem a identidades clínicas confirmadas; não foram unificadas automaticamente.
- Estrutura completa: `relatorios/estrutura.txt`; agrupamento: `relatorios/pacientes.csv`; cópias idênticas: `relatorios/duplicatas.json`. Pastas sem STL continuam listadas na estrutura.

## Inventário

`inventario.csv` contém uma linha por STL: triângulos, vértices únicos, mínimos/máximos/dimensões XYZ, centroide de superfície ponderado por área, área, eixos/autovalores PCA, SHA-256, fechamento e indícios de base.

STL não armazena unidade. As coordenadas são nativas e interpretadas provisoriamente como mm; não houve reescala. Centroide é da superfície, não média dos vértices nem centro de massa volumétrico. Fechamento é avaliado unindo vértices de coordenadas exatamente iguais e verificando incidência de duas faces por aresta; não certifica ausência de autointerseção ou orientação consistente. Resultado: {c['watertight']}.

Base de gesso: **INDETERMINADA para cada arquivo**. O indício automático de superfície plana está em coluna separada e não confirma presença/ausência de base. As nove prévias amostradas (`relatorios/previas.png`) mostram superfícies de arcadas com extensão variável; não permitem classificar com segurança bases em todo o conjunto. Não foi realizado corte. É necessária anotação visual por arquivo antes de usar este campo como verdade de referência.

## Orientação PCA

Momentos exatos da superfície triangular, ponderados por área, eixos em ordem decrescente dos autovalores. Dispersão calculada entre todos os pares da mesma categoria de arcada, removendo cópias SHA-256 e pares da mesma pasta; menor ângulo de rotação entre as quatro combinações próprias de sinais. Não se misturam superiores e inferiores. Valores indeterminados são apresentados separadamente e podem misturar anatomias.

| Categoria | Pares | Mínimo (°) | Mediana (°) | Máximo (°) |
|---|---:|---:|---:|---:|
{table}

**{c['pca']['conclusao']}** O limite de 10° é uma heurística PLACEHOLDER, não limiar validado. PCA não prova alinhamento anatômico: diferenças de forma, base e autovalores próximos podem mudar eixos; sinais removem evidência de giros de 180°. Os resultados não demonstram alinhamento oclusal entre superior/inferior do mesmo paciente. Pares auditáveis em `relatorios/pca_pares.csv`.

## Parâmetros de treino e próximos passos

`config.json` registra achados e **PLACEHOLDER** para projeção, FOV/extensão ortográfica, posição/direção/up das seis câmeras (inclusive ângulo da Angulada), distância, resolução, fundo, luz, material, centralização, escala, orientação canônica e tratamento das bases. Fotografias e capturas presentes não recuperam esses parâmetros com exatidão. Nenhum referencial anatômico, plano de Frankfort ou alinhamento por Ruellas foi confirmado.

Esta entrega conclui a inspeção solicitada antes da interface. Para reproduzir o treino serão necessários o script original ou sua configuração e um template validado. Não é possível garantir equivalência das seis vistas usando placeholders.

## Reprodução

Requer Python 3 e NumPy; `tar` com suporte RAR para os arquivos internos. Execute `python3 "scripts/inspecionar.py"` e depois `python3 "scripts/resumir.py"`. O inventário existente é usado como cache, validado por SHA-256 antes da reutilização. Prévia opcional com Matplotlib: `python3 "scripts/previas.py"`.

**Real:** extração, hashes, estatísticas de malha, PCA e comparação dos eixos. **Heurístico:** categoria por nome e indício de plano. **Não confirmado:** unidade mm, bases, identidade entre pastas e pose anatômica. **PLACEHOLDER:** parâmetros de treino/câmeras; interface e normalização PCA+ICP ainda não implementadas nesta etapa.
'''
(root/'README.md').write_text(text)
print(json.dumps({k:c[k] for k in ['stl','stl_unicos_sha256','pastas_paciente_com_stl','arcadas','watertight','pca']},ensure_ascii=False,indent=2))
