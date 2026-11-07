"""Etapas do pipeline que tocam o banco: salvar coleta, processar fila e gerar alertas."""

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from radar.collectors.base import Coletor, ErroColeta, PublicacaoColetada
from radar.db import session_scope
from radar.models import Acompanhamento, Alerta, Cargo, Coleta, Edital, Filtro, Publicacao, Usuario
from radar.pipeline.detector import detectar
from radar.pipeline.extractor import EditalExtraido, ErroExtracao, Extrator, parse_data
from radar.pipeline.matcher import CargoInfo, EditalInfo, FiltroInfo, casar
from radar.texto import normalizar

log = logging.getLogger(__name__)

TIPOS_LIGADOS_A_OUTRO_EDITAL = {
    "retificacao",
    "prorrogacao",
    "cancelamento",
    "resultado",
    "convocacao",
    "homologacao",
}


def agora() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
def coletar_fonte(coletor: Coletor, dia: date) -> tuple[int, int]:
    """Roda um coletor para um dia e grava as publicações novas. Devolve (lidos, novos)."""
    with session_scope() as s:
        conhecidos = set(
            s.scalars(
                select(Publicacao.id_externo).where(
                    Publicacao.fonte == coletor.fonte, Publicacao.data_publicacao >= dia
                )
            )
        )
        coleta = Coleta(fonte=coletor.fonte, data_ref=dia)
        s.add(coleta)
        s.flush()
        coleta_id = coleta.id

    lidos = novos = 0
    erro: str | None = None
    try:
        for item in coletor.coletar(dia, ja_conhecido=conhecidos.__contains__):
            lidos += 1
            if salvar_publicacao(item):
                novos += 1
            conhecidos.add(item.id_externo)
    except ErroColeta as e:
        erro = str(e)
        log.error("coleta %s %s: %s", coletor.fonte, dia, e)
    except Exception as e:  # rede, HTML inesperado etc. - não derruba o worker
        erro = f"{type(e).__name__}: {e}"
        log.exception("coleta %s %s falhou", coletor.fonte, dia)

    with session_scope() as s:
        coleta = s.get(Coleta, coleta_id)
        coleta.finalizada_em = agora()
        coleta.itens_lidos = lidos
        coleta.itens_novos = novos
        coleta.erro = erro
    log.info("coleta %s %s: %s candidatas, %s novas", coletor.fonte, dia, lidos, novos)
    return lidos, novos


def salvar_publicacao(item: PublicacaoColetada) -> bool:
    with session_scope() as s:
        resultado = s.execute(
            insert(Publicacao)
            .values(
                fonte=item.fonte,
                id_externo=item.id_externo,
                data_publicacao=item.data_publicacao,
                secao=item.secao,
                orgao=item.orgao,
                tipo_ato=item.tipo_ato,
                titulo=item.titulo,
                url=item.url,
                texto=item.texto,
                hash_texto=hashlib.sha256(item.texto.encode()).hexdigest(),
            )
            .on_conflict_do_nothing(index_elements=["fonte", "id_externo"])
            .returning(Publicacao.id)
        )
        return resultado.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Processamento da fila
# ---------------------------------------------------------------------------
def processar_pendentes(extrator: Extrator, max_tentativas: int, limite: int = 200) -> int:
    """Pega publicações pendentes uma a uma (SKIP LOCKED permite vários workers em paralelo)."""
    tentadas: set[int] = set()
    processadas = 0
    while processadas < limite:
        with session_scope() as s:
            consulta = (
                select(Publicacao)
                .where(Publicacao.status == "pendente")
                .order_by(Publicacao.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if tentadas:
                consulta = consulta.where(Publicacao.id.not_in(tentadas))
            pub = s.scalars(consulta).first()
            if pub is None:
                break
            tentadas.add(pub.id)
            processar_publicacao(s, pub, extrator, max_tentativas)
            processadas += 1
    return processadas


def processar_publicacao(s: Session, pub: Publicacao, extrator: Extrator, max_tentativas: int) -> None:
    deteccao = detectar(pub.titulo or "", pub.texto)
    pub.score_detector = deteccao.score
    if not deteccao.candidato:
        _finalizar(pub, "descartada")
        return

    try:
        extraido = extrator.extrair(
            fonte=pub.fonte, data=pub.data_publicacao, orgao=pub.orgao, titulo=pub.titulo, texto=pub.texto
        )
    except ErroExtracao as e:
        pub.tentativas += 1
        pub.erro = str(e)
        pub.status = "erro" if pub.tentativas >= max_tentativas else "pendente"
        log.warning("publicação %s: %s (tentativa %s)", pub.id, e, pub.tentativas)
        return

    if not extraido.e_concurso or extraido.tipo == "outro":
        _finalizar(pub, "descartada")
        return

    edital = salvar_edital(s, pub, extraido, extrator.modelo)
    _finalizar(pub, "processada")
    criados = gerar_alertas(s, edital)
    log.info("edital %s (%s) %s: %s alertas", edital.id, edital.tipo, edital.titulo, criados)


def _finalizar(pub: Publicacao, status: str) -> None:
    pub.status = status
    pub.erro = None
    pub.processada_em = agora()


def salvar_edital(s: Session, pub: Publicacao, ex: EditalExtraido, modelo: str) -> Edital:
    salarios = [c.salario for c in ex.cargos if c.salario is not None]
    vagas = [c.vagas for c in ex.cargos if c.vagas is not None]
    edital = Edital(
        publicacao_id=pub.id,
        tipo=ex.tipo,
        orgao=ex.orgao or pub.orgao,
        banca=ex.banca,
        titulo=ex.titulo or pub.titulo,
        numero_edital=ex.numero_edital,
        edital_referenciado=ex.edital_referenciado,
        uf=(ex.uf or "").upper()[:2] or None,
        cidades=ex.cidades,
        inscricao_inicio=parse_data(ex.inscricao_inicio),
        inscricao_fim=parse_data(ex.inscricao_fim),
        data_prova=parse_data(ex.data_prova),
        taxa_inscricao=_decimal(ex.taxa_inscricao),
        salario_max=_decimal(max(salarios)) if salarios else None,
        vagas_total=sum(vagas) if vagas else None,
        link_inscricao=ex.link_inscricao,
        resumo=ex.resumo,
        dados=ex.model_dump(mode="json"),
        modelo=modelo,
        cargos=[
            Cargo(
                nome=c.nome,
                escolaridade=c.escolaridade,
                vagas=c.vagas,
                cadastro_reserva=c.cadastro_reserva,
                salario=_decimal(c.salario),
            )
            for c in ex.cargos
        ],
    )
    if ex.tipo in TIPOS_LIGADOS_A_OUTRO_EDITAL:
        edital.edital_pai_id = encontrar_edital_pai(s, edital)
    s.add(edital)
    s.flush()
    return edital


def _decimal(valor: float | None) -> Decimal | None:
    return Decimal(str(round(valor, 2))) if valor is not None else None


def chave_numero_edital(numero: str | None) -> str | None:
    """'EDITAL Nº 01/2026 - SEEDF' -> '1/2026'"""
    if not numero:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d{4})", numero)
    if m:
        return f"{int(m.group(1))}/{m.group(2)}"
    m = re.search(r"n[ºo°.]*\s*(\d+)", normalizar(numero))
    return str(int(m.group(1))) if m else None


def encontrar_edital_pai(s: Session, edital: Edital) -> int | None:
    chave = chave_numero_edital(edital.edital_referenciado)
    if not chave or not edital.orgao:
        return None
    orgao = normalizar(edital.orgao)
    candidatos = s.execute(
        select(Edital.id, Edital.orgao, Edital.numero_edital)
        .where(Edital.tipo == "abertura", Edital.numero_edital.is_not(None))
        .order_by(Edital.id.desc())
        .limit(500)
    )
    for id_, orgao_cand, numero_cand in candidatos:
        if chave_numero_edital(numero_cand) != chave:
            continue
        o = normalizar(orgao_cand or "")
        if o and (o in orgao or orgao in o):
            return id_
    return None


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
def edital_para_info(edital: Edital) -> EditalInfo:
    return EditalInfo(
        titulo=edital.titulo,
        orgao=edital.orgao,
        uf=edital.uf,
        resumo=edital.resumo,
        cargos=[CargoInfo(c.nome, c.escolaridade, c.salario) for c in edital.cargos],
    )


def filtro_para_info(filtro: Filtro) -> FiltroInfo:
    return FiltroInfo(filtro.palavras, filtro.ufs, filtro.escolaridades, filtro.salario_min)


def gerar_alertas(s: Session, edital: Edital) -> int:
    hoje = date.today()
    usuarios: set[int] = set()

    if edital.tipo == "abertura":
        if edital.inscricao_fim and edital.inscricao_fim < hoje:
            return 0  # inscrições já encerradas (ex.: reprocessamento de dias antigos)
        info = edital_para_info(edital)
        filtros = s.scalars(select(Filtro).join(Usuario).where(Filtro.ativo, Usuario.ativo))
        for filtro in filtros:
            if filtro.usuario_id not in usuarios and casar(info, filtro_para_info(filtro)):
                usuarios.add(filtro.usuario_id)
        motivo = "novo_edital"
    elif edital.edital_pai_id:
        usuarios = set(
            s.scalars(
                select(Acompanhamento.usuario_id)
                .join(Usuario, Usuario.id == Acompanhamento.usuario_id)
                .where(Acompanhamento.edital_id == edital.edital_pai_id, Usuario.ativo)
            )
        )
        motivo = "retificacao"
    else:
        return 0

    if not usuarios:
        return 0
    s.execute(
        insert(Alerta)
        .values([{"usuario_id": u, "edital_id": edital.id, "motivo": motivo} for u in usuarios])
        .on_conflict_do_nothing(index_elements=["usuario_id", "edital_id"])
    )
    return len(usuarios)
