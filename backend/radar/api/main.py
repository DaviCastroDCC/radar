"""API pública de leitura (base para o site Next.js) e métricas do produto.

Rodar: uvicorn radar.api.main:app --host 0.0.0.0 --port 8000
"""

from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from radar.db import session_scope
from radar.models import Edital, Publicacao

app = FastAPI(title="Radar Concurso", version="0.1.0")


class CargoOut(BaseModel):
    nome: str
    escolaridade: str
    vagas: int | None
    cadastro_reserva: bool
    salario: Decimal | None


class EditalResumo(BaseModel):
    id: int
    tipo: str
    titulo: str | None
    orgao: str | None
    banca: str | None
    uf: str | None
    salario_max: Decimal | None
    vagas_total: int | None
    inscricao_inicio: date | None
    inscricao_fim: date | None
    data_prova: date | None
    fonte: str
    data_publicacao: date
    url_publicacao: str | None


class EditalDetalhe(EditalResumo):
    numero_edital: str | None
    cidades: list[str]
    taxa_inscricao: Decimal | None
    link_inscricao: str | None
    resumo: str | None
    edital_pai_id: int | None
    cargos: list[CargoOut]


def _resumo(e: Edital) -> dict:
    return {
        **{k: getattr(e, k) for k in EditalResumo.model_fields if hasattr(e, k)},
        "fonte": e.publicacao.fonte,
        "data_publicacao": e.publicacao.data_publicacao,
        "url_publicacao": e.publicacao.url,
    }


@app.get("/health")
def health() -> dict[str, str]:
    with session_scope() as s:
        s.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/editais", response_model=list[EditalResumo])
def listar_editais(
    q: str | None = Query(None, description="Busca textual: cargo, órgão, banca"),
    uf: str | None = None,
    tipo: str = "abertura",
    abertos: bool = Query(False, description="Só com inscrições ainda abertas"),
    limite: int = Query(20, le=100),
    pagina: int = Query(1, ge=1),
) -> list[dict]:
    with session_scope() as s:
        consulta = (
            select(Edital)
            .join(Publicacao)
            .options(selectinload(Edital.publicacao))
            .where(Edital.tipo == tipo)
        )
        if q:
            consulta = consulta.where(text("editais.tsv @@ websearch_to_tsquery('pt', :q)").bindparams(q=q))
        if uf:
            consulta = consulta.where(Edital.uf.in_([uf.upper(), "BR"]))
        if abertos:
            consulta = consulta.where(
                (Edital.inscricao_fim.is_(None)) | (Edital.inscricao_fim >= date.today())
            )
        consulta = consulta.order_by(Publicacao.data_publicacao.desc(), Edital.id.desc())
        consulta = consulta.limit(limite).offset((pagina - 1) * limite)
        return [_resumo(e) for e in s.scalars(consulta)]


@app.get("/editais/{edital_id}", response_model=EditalDetalhe)
def detalhe_edital(edital_id: int) -> dict:
    with session_scope() as s:
        e = s.scalar(
            select(Edital)
            .where(Edital.id == edital_id)
            .options(selectinload(Edital.publicacao), selectinload(Edital.cargos))
        )
        if e is None:
            raise HTTPException(404, "Edital não encontrado")
        return {
            **_resumo(e),
            "numero_edital": e.numero_edital,
            "cidades": e.cidades,
            "taxa_inscricao": e.taxa_inscricao,
            "link_inscricao": e.link_inscricao,
            "resumo": e.resumo,
            "edital_pai_id": e.edital_pai_id,
            "cargos": [CargoOut.model_validate(c, from_attributes=True) for c in e.cargos],
        }


METRICAS_SQL = text("""
SELECT
  (SELECT count(*) FROM usuarios WHERE ativo)                         AS usuarios_ativos,
  (SELECT count(*) FROM filtros WHERE ativo)                          AS filtros_ativos,
  (SELECT coalesce(sum(itens_lidos), 0) FROM coletas)                 AS publicacoes_candidatas_lidas,
  (SELECT count(*) FROM publicacoes)                                  AS publicacoes_armazenadas,
  (SELECT count(*) FROM editais)                                      AS editais_processados,
  (SELECT count(*) FROM editais WHERE tipo = 'abertura')              AS editais_de_abertura,
  (SELECT count(*) FROM alertas WHERE status = 'enviado')             AS alertas_enviados,
  (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM a.enviado_em - p.coletada_em))
     FROM alertas a JOIN editais e ON e.id = a.edital_id JOIN publicacoes p ON p.id = e.publicacao_id
    WHERE a.status = 'enviado')                                       AS latencia_p50_s,
  (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM a.enviado_em - p.coletada_em))
     FROM alertas a JOIN editais e ON e.id = a.edital_id JOIN publicacoes p ON p.id = e.publicacao_id
    WHERE a.status = 'enviado')                                       AS latencia_p95_s
""")


@app.get("/metricas")
def metricas() -> dict:
    """Números para o banner: usuários, editais lidos, alertas e latência coleta -> alerta."""
    with session_scope() as s:
        linha = s.execute(METRICAS_SQL).mappings().one()
        ultimas_coletas = (
            s.execute(
                text("""
                SELECT DISTINCT ON (fonte) fonte, data_ref, finalizada_em, itens_lidos, itens_novos, erro
                FROM coletas ORDER BY fonte, id DESC
            """)
            )
            .mappings()
            .all()
        )
    return {
        **{k: (float(v) if isinstance(v, Decimal) else v) for k, v in linha.items()},
        "ultimas_coletas": [dict(c) for c in ultimas_coletas],
    }
