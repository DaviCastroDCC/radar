# Avaliação da extração por IA

O maior risco do produto é a IA errar um dado que o concurseiro usa para decidir (salário,
prazo de inscrição). Esta pasta mede esse risco com publicações reais, antes do lançamento e
a cada troca de modelo ou de prompt.

## Critérios de lançamento (definidos ANTES de ver os resultados)

| Critério | Mínimo para lançar | Por quê |
|---|---|---|
| `ok_classificacao` | **95%** | Classificar errado = alerta falso ou concurso perdido |
| `ok_datas` | **95%** | Prazo de inscrição errado é o erro mais caro para o usuário |
| `ok_salario` | 90% | Filtro de salário depende dele |
| `ok_cargos` | 90% | Base do matching por cargo |
| `ok_orgao_banca`, `ok_vagas`, `ok_taxa` | 85% | Informativos na mensagem |

Use o **limite inferior do IC 95%** para decidir quando a amostra for pequena: com 30 editais,
90% de acerto observado pode ser só 74% de verdade.

## Passo a passo

Rode tudo dentro do container (`docker compose run --rm worker ...`).

```bash
# 1. Corpus: publicações reais que o detector mandaria para a IA (sem custo)
python -m radar.avaliacao coletar --de 2026-09-01 --ate 2026-11-06

# 2. Extração (custo: ~US$ 0,003 por publicação com o Haiku). Pode interromper e retomar.
python -m radar.avaliacao rodar

# 3. Planilha de revisão em avaliacao/revisoes/<modelo>-<data>.csv
python -m radar.avaliacao planilha
```

4. Abra o CSV no Excel ou Google Sheets. Para cada linha, abra o `url` (publicação original)
   e marque as colunas `ok_*` com **S** (certo), **N** (errado) ou **NA** (não se aplica,
   ex.: taxa num edital de retificação). Anote o erro em `observacoes`.

```bash
# 5. Resultado
python -m radar.avaliacao pontuar avaliacao/revisoes/<arquivo>.csv
```

## O que vai para o git

| Pasta | Versionada? | Motivo |
|---|---|---|
| `corpus/` | Não | Texto integral das publicações pode ter nomes de candidatos (LGPD) |
| `resultados/` | Não | Saída bruta, reprodutível a partir do corpus |
| `revisoes/` | **Sim** | É o gabarito: permite comparar modelos e prompts no futuro |

## Quando rodar de novo

- Troca de modelo (`EXTRACTOR_MODEL`) ou de esforço (`EXTRACTOR_EFFORT`).
- Mudança no prompt ou no schema em `radar/pipeline/extractor.py`.
- Nova fonte de dados (DOU, bancas, diários estaduais).
