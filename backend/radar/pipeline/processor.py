"""Etapas do pipeline que tocam o banco: salvar coleta, processar fila e gerar alertas."""

import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from radar.collectors import FONTES_DIARIOS
from radar.collectors.base import Coletor, ErroColeta, PublicacaoColetada
from radar.db import session_scope
from radar.models import Acompanhamento, Alerta, Cargo, Coleta, Edital, Filtro, Publicacao, Usuario
from radar.pipeline.dedup import mesmo_concurso, numero_e_ano
from radar.pipeline.detector import detectar
from radar.pipeline.extractor import EditalExtraido, ErroExtracao, Extrator, parse_data
from radar.pipeline.matcher import CargoInfo, EditalInfo, FiltroInfo, casar
from radar.relogio import agora
from radar.usuarios import pode_receber_alertas

log = logging.getLogger(__name__)

TIPOS_LIGADOS_A_OUTRO_EDITAL = {
    "retificacao",
    "prorrogacao",
    "cancelamento",
    "resultado",
    "convocacao",
    "homologacao",
}


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
def coletada_recentemente(fonte: str, minutos: int) -> bool:
    with session_scope() as s:
        ultima = s.scalar(select(func.max(Coleta.iniciada_em)).where(Coleta.fonte == fonte))
    return ultima is not None and agora() - ultima < timedelta(minutes=minutos)


def coletar_fonte(coletor: Coletor, dia: date) -> tuple[int, int]:
    """Roda um coletor para um dia e grava as publicações novas. Devolve (lidos, novos)."""
    with session_scope() as s:
        conhecidos = set(
            s.scalars(
                select(Publicacao.id_externo).where(
                    Publicacao.fonte == coletor.fonte,
                    # Bancas olham uma janela de dias para trás; diários, só o próprio dia.
                    Publicacao.data_publicacao >= dia - timedelta(days=getattr(coletor, "janela_dias", 0)),
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
        log.error("coleta recusada: %s", e, extra={"fonte": coletor.fonte, "dia": dia})
    except Exception as e:  # rede, HTML inesperado etc. - não derruba o worker
        erro = f"{type(e).__name__}: {e}"
        log.exception("coleta falhou", extra={"fonte": coletor.fonte, "dia": dia})

    with session_scope() as s:
        coleta = s.get(Coleta, coleta_id)
        coleta.finalizada_em = agora()
        coleta.itens_lidos = lidos
        coleta.itens_novos = novos
        coleta.erro = erro
    log.info(
        "coleta concluída",
        extra={"fonte": coletor.fonte, "dia": dia, "candidatas": lidos, "novas": novos, "erro": erro},
    )
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
    # O detector filtra DIÁRIOS, onde quase nada é concurso. Em bancas tudo é concurso e
    # uma retificação curta nem repete "concurso público": a fonte já é o sinal, a IA decide.
    if not deteccao.candidato and pub.fonte in FONTES_DIARIOS:
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
        log.warning("extração falhou: %s", e, extra={"publicacao_id": pub.id, "tentativa": pub.tentativas})
        return

    if not extraido.e_concurso or extraido.tipo == "outro":
        _finalizar(pub, "descartada")
        return

    edital = salvar_edital(s, pub, extraido, extrator.modelo)
    _finalizar(pub, "processada")
    criados = gerar_alertas(s, edital)
    log.info(
        "edital processado: %s",
        edital.titulo,
        extra={"edital_id": edital.id, "tipo": edital.tipo, "fonte": pub.fonte, "alertas": criados},
    )


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
        edital.edital_pai_id = _abertura_correspondente(s, edital.orgao, edital.edital_referenciado)
    elif ex.tipo == "abertura":
        # Mesmo edital de abertura já visto por outra fonte (ex.: banca e DOU)?
        edital.duplicata_de_id = _abertura_correspondente(s, edital.orgao, edital.numero_edital)
    s.add(edital)
    s.flush()
    return edital


def _decimal(valor: float | None) -> Decimal | None:
    return Decimal(str(round(valor, 2))) if valor is not None else None


JANELA_DEDUP = timedelta(days=180)


def _abertura_correspondente(s: Session, orgao: str | None, numero: str | None) -> int | None:
    """Edital de abertura ORIGINAL (não duplicata) com mesmo órgão e número, nos últimos meses."""
    if not orgao or not numero_e_ano(numero):
        return None
    candidatos = s.execute(
        select(Edital.id, Edital.orgao, Edital.numero_edital)
        .where(
            Edital.tipo == "abertura",
            Edital.numero_edital.is_not(None),
            Edital.duplicata_de_id.is_(None),
            Edital.criado_em > agora() - JANELA_DEDUP,
        )
        .order_by(Edital.id)
    )
    for id_, orgao_cand, numero_cand in candidatos:
        if mesmo_concurso(orgao, numero, orgao_cand, numero_cand):
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

    if edital.duplicata_de_id:
        return 0  # quem se interessa já foi avisado pela primeira fonte que publicou
    if edital.tipo == "abertura":
        if edital.inscricao_fim and edital.inscricao_fim < hoje:
            return 0  # inscrições já encerradas (ex.: reprocessamento de dias antigos)
        info = edital_para_info(edital)
        filtros = s.scalars(select(Filtro).join(Usuario).where(Filtro.ativo, pode_receber_alertas()))
        for filtro in filtros:
            if filtro.usuario_id not in usuarios and casar(info, filtro_para_info(filtro)):
                usuarios.add(filtro.usuario_id)
        motivo = "novo_edital"
    elif edital.edital_pai_id:
        usuarios = set(
            s.scalars(
                select(Acompanhamento.usuario_id)
                .join(Usuario, Usuario.id == Acompanhamento.usuario_id)
                .where(Acompanhamento.edital_id == edital.edital_pai_id, pode_receber_alertas())
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
