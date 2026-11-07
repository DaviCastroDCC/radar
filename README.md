# Radar Concurso

[![CI](https://github.com/DaviCastroDCC/radar/actions/workflows/ci.yml/badge.svg)](https://github.com/DaviCastroDCC/radar/actions/workflows/ci.yml)

Lê os diários oficiais todo dia, entende os editais de concurso com IA e avisa cada pessoa,
pelo Telegram, só do que importa para ela: cargo, região, escolaridade e salário. Também avisa
quando sai retificação de um edital que a pessoa acompanha.

## Arquitetura

```
 DODF (JSON + HTML) ─┐
                     ├─► coletores ─► pré-filtro ─► publicacoes (fila no Postgres, SKIP LOCKED)
 DOU (INLABS, XML) ──┘                                     │
                                                           ▼
                                   detector (regras, sem custo) ─► descarta ~90%
                                                           │
                                                           ▼
                                   extrator (Claude Haiku, JSON validado por Pydantic)
                                                           │
                                                           ▼
                           editais + cargos ─► matcher (filtros dos usuários) ─► alertas
                                                                                    │
                                    bot do Telegram ◄── cadastro/filtros   envio ◄──┘
                                    API (FastAPI)   ──► site, métricas
```

| Peça | Onde |
|---|---|
| Schema do banco (migrations Alembic) | [backend/migrations/](backend/migrations/) |
| Coletores | [backend/radar/collectors/](backend/radar/collectors/) |
| Detector, extrator, matcher, fila | [backend/radar/pipeline/](backend/radar/pipeline/) |
| Envio dos alertas | [backend/radar/notify/](backend/radar/notify/) |
| Bot do Telegram | [backend/radar/bot/](backend/radar/bot/) |
| API e métricas | [backend/radar/api/main.py](backend/radar/api/main.py) |
| Worker (orquestra o ciclo) | [backend/radar/worker.py](backend/radar/worker.py) |

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 17 (busca textual em português sem
acento + pgvector reservado), python-telegram-bot, SDK da Anthropic, Docker.

## Fontes

Meta atual: **DOU + as 10 maiores bancas**. Só coletamos o que o `robots.txt` permite e nunca
contornamos bloqueio: concursos de bancas fechadas chegam pelos diários oficiais, onde o órgão
contratante é obrigado a publicar.

| Fonte | Status | Observação |
|---|---|---|
| DODF | ✅ coletando | JSON interno do site, todo ciclo |
| DOU (INLABS) | ✅ pronto | Precisa de `INLABS_EMAIL`/`INLABS_PASSWORD` (cadastro gratuito) |
| Cebraspe | ✅ coletando | API JSON pública + PDFs; a cada 30 min |
| FGV, Cesgranrio, Instituto AOCP, Consulplan | 🔜 próximas | Sites liberados no `robots.txt` |
| Quadrix, Idecan | 🔜 próximas | Liberados para robôs em geral (bloqueiam só treino de IA, que não fazemos) |
| FCC | ⛔ não coletar | `robots.txt` proíbe `/concursos/` e PDFs; cobertura via DOU/diários |
| Vunesp, IBFC | ⛔ não coletar | Bloqueiam robôs (403); cobertura via DOU/diários |

Detalhes de cada fonte de banca:

- Só entram documentos que mudam a vida do candidato (abertura, retificação, prorrogação,
  suspensão). Resultados e listas de candidatos ficam de fora: são enormes e cheios de dados pessoais.
- O mesmo concurso vindo de duas fontes (banca + DOU) gera **um** alerta
  ([radar/pipeline/dedup.py](backend/radar/pipeline/dedup.py)). Na dúvida, não junta: alerta
  duplicado é melhor que concurso perdido.
- Nova banca = uma classe com `listar_documentos()` em
  [radar/collectors/bancas/](backend/radar/collectors/bancas/) + registro em `radar/collectors/__init__.py`.

## Rodando

Pré-requisito: Docker Desktop. Para produção, veja [deploy/README.md](deploy/README.md).

```bash
cp .env.example .env       # preencha as chaves (veja abaixo)
docker compose up -d       # db + worker + bot + api
docker compose logs -f worker
```

| Variável | Para quê | Como conseguir |
|---|---|---|
| `ANTHROPIC_API_KEY` | extração dos editais | console.anthropic.com |
| `TELEGRAM_BOT_TOKEN` | bot e alertas | @BotFather no Telegram, comando `/newbot` |
| `INLABS_EMAIL` / `INLABS_PASSWORD` | DOU | cadastro gratuito em inlabs.in.gov.br |

Sem as credenciais do INLABS, use `FONTES=dodf` para coletar só o DODF.

### Comandos úteis

```bash
# testes (unitários + integração com Postgres real)
docker compose run --rm api pytest

# coletar um dia específico (reprocessamento / histórico)
docker compose run --rm worker python -m radar.worker coletar --fonte dodf --data 2026-11-06

# rodar só uma etapa
docker compose run --rm worker python -m radar.worker processar
docker compose run --rm worker python -m radar.worker notificar

# API
curl localhost:8000/metricas
curl "localhost:8000/editais?q=analista&uf=DF&abertos=true"
```

### Bot

```
/start
/filtro analista ti; uf=DF,GO; salario=6000; escolaridade=superior
/filtros
/remover 3
/parar
/privacidade
/meusdados
/apagar
```

Cada alerta vem com o botão **Acompanhar retificações**.

## Privacidade (LGPD)

| Requisito | Como o sistema atende |
|---|---|
| Consentimento (art. 7º, I) | Aceite explícito no `/start`, com data e versão gravadas; sem aceite, nada de filtros nem alertas |
| Nova versão da política | Subir `TERMOS_VERSAO` em [radar/usuarios.py](backend/radar/usuarios.py) pede novo aceite a todos |
| Acesso e portabilidade (art. 18) | `/meusdados` envia um JSON com tudo o que guardamos |
| Eliminação (art. 18) | `/apagar` remove o usuário; filtros, alertas e acompanhamentos saem em cascata |
| Minimização (art. 6º, III) | Só o `chat_id`; nome e telefone não são guardados |
| Retenção | Inativos (bloqueio ou `/parar`) são apagados após 180 dias pelo worker |

Política completa: [docs/PRIVACIDADE.md](docs/PRIVACIDADE.md). Revise-a com um profissional
jurídico antes do lançamento público.

## Desenvolvimento

- **Qualidade:** `ruff` (lint e formatação) e `pytest` com cobertura mínima de 88%. Tudo roda no CI
  (GitHub Actions) a cada push e PR, com Postgres de verdade para os testes de integração.
- **Hooks locais:** `pip install pre-commit && pre-commit install`.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/pt-br/)
  (`feat:`, `fix:`, `test:`, `ci:`, `docs:`...).
- **Fluxo:** branch a partir de `main`, PR com o template, merge só com CI verde.

```bash
docker compose run --rm api sh -c "ruff format . && ruff check . && pytest --cov"
```

### Migrations (Alembic)

O serviço `migrate` aplica as migrations a cada `docker compose up`, antes dos demais.
Para mudar o schema:

```bash
# 1. altere radar/models.py
# 2. gere o rascunho e REVISE o arquivo criado em backend/migrations/versions/
docker compose run --rm migrate alembic revision --autogenerate -m "descricao curta"
# 3. aplique e teste
docker compose run --rm migrate alembic upgrade head
docker compose run --rm api pytest tests/test_migrations.py
```

Regras: toda migration tem `downgrade`; nunca edite uma migration já mergeada na `main`;
o teste `test_models_sincronizados_com_as_migrations` quebra se models e banco divergirem.

## Métricas (para o banner)

`GET /metricas` devolve usuários ativos, publicações lidas, editais processados, alertas enviados
e a latência p50/p95 entre a coleta e o alerta. Tudo sai das tabelas, sem instrumentação extra.

## Operação e alarmes

O worker se autodiagnostica a cada ciclo e avisa no Telegram do admin (`ADMIN_CHAT_ID`)
**quando um problema abre e quando resolve**, nunca repetidamente.

| Alarme | Severidade | Quando dispara |
|---|---|---|
| `worker_parado` | crítico | Nenhum ciclo há mais de 3× o intervalo |
| `coleta_falhando:<fonte>` | crítico | 3 coletas seguidas com erro (site fora, login recusado...) |
| `coleta_zerada:<fonte>` | aviso | Dia útil, após as 10h, sem nenhuma publicação candidata (feriado ou site mudou) |
| `fila_parada` | crítico | Publicações esperando extração há mais de 1h (API da IA fora, chave inválida) |
| `extracao_falhando` | aviso | 5+ publicações desistiram da extração em 24h |
| `envio_parado` | crítico | Alertas esperando envio há mais de 30 min |
| `etapa_falhou:<etapa>` | crítico | Uma etapa do ciclo lançou exceção (as demais continuam rodando) |

- `GET /saude` responde **503** com problema crítico. Aponte um monitor externo gratuito
  (UptimeRobot, Healthchecks.io) para ele: é o que avisa se o próprio worker morrer.
- `docker compose run --rm worker python -m radar.worker saude` mostra o diagnóstico no terminal.
- `LOG_FORMAT=json` gera uma linha JSON por evento (com tokens gastos na IA por extração),
  pronta para CloudWatch, Loki ou Datadog.

## Próximos passos

- [x] Migrations (Alembic), LGPD e alarmes operacionais
- [ ] Rodar alguns dias com dados reais e revisar à mão ~50 extrações (qualidade da IA)
- [ ] Site Next.js com uma página por edital (SEO) consumindo a API
- [ ] Bancas: Cebraspe, FGV, FCC, Cesgranrio
- [ ] Diários estaduais e municipais (via Querido Diário)
- [ ] Plano Premium (Pix/cartão), alerta instantâneo e WhatsApp
- [ ] Busca semântica de cargos com pgvector
- [x] Deploy em VM única com HTTPS, backup e restauração testada ([deploy/README.md](deploy/README.md))
- [ ] Escalar para AWS (ECS Fargate + RDS; fila em SQS) quando a carga pedir
