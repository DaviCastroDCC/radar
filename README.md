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

## Rodando

Pré-requisito: Docker Desktop.

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
```

Cada alerta vem com o botão **Acompanhar retificações**.

## Desenvolvimento

- **Qualidade:** `ruff` (lint e formatação) e `pytest` com cobertura mínima de 74%. Tudo roda no CI
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

## Próximos passos

- [ ] Rodar alguns dias com dados reais e revisar à mão ~50 extrações (qualidade da IA)
- [ ] Site Next.js com uma página por edital (SEO) consumindo a API
- [ ] Bancas: Cebraspe, FGV, FCC, Cesgranrio
- [ ] Diários estaduais e municipais (via Querido Diário)
- [ ] Plano Premium (Pix/cartão), alerta instantâneo e WhatsApp
- [ ] Busca semântica de cargos com pgvector
- [ ] Deploy na AWS (ECS Fargate + RDS; trocar a fila do Postgres por SQS quando o volume pedir)
