"""Diagnóstico da saúde do sistema: o que está quebrado agora?

Cada verificação devolve um Problema com uma chave estável (ex.: "coleta_falhando:dodf").
A chave é o que permite abrir/resolver alarmes sem repetir avisos (ver radar.alarmes).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from radar.collectors import FONTES_DIARIOS
from radar.config import Settings
from radar.models import Alarme, Alerta, Coleta, Publicacao
from radar.relogio import agora

FUSO = ZoneInfo("America/Sao_Paulo")

FALHAS_SEGUIDAS_PARA_ALARME = 3
FILA_PARADA_APOS = timedelta(hours=1)
ENVIO_PARADO_APOS = timedelta(minutes=30)
ERROS_DE_EXTRACAO_EM_24H = 5

Severidade = Literal["aviso", "critico"]


@dataclass(frozen=True)
class Problema:
    chave: str
    severidade: Severidade
    mensagem: str


def diagnosticar(s: Session, settings: Settings, referencia: datetime | None = None) -> list[Problema]:
    ref = referencia or agora()
    problemas: list[Problema] = []
    problemas += _worker(s, settings, ref)
    for fonte in settings.lista_fontes:
        problemas += _coleta(s, settings, fonte, ref)
    problemas += _filas(s, ref)
    return problemas


def problemas_atuais(s: Session, settings: Settings, referencia: datetime | None = None) -> list[Problema]:
    """Diagnóstico ao vivo + alarmes abertos pelo worker que só ele consegue detectar
    (ex.: etapa que lançou exceção). É a visão usada pelo /saude e pelo comando `saude`."""
    vivos = diagnosticar(s, settings, referencia)
    chaves = {p.chave for p in vivos}
    abertos = s.scalars(select(Alarme).where(Alarme.resolvido_em.is_(None)).order_by(Alarme.id))
    return vivos + [Problema(a.chave, a.severidade, a.mensagem) for a in abertos if a.chave not in chaves]


def _worker(s: Session, settings: Settings, ref: datetime) -> list[Problema]:
    ultima = s.scalar(select(func.max(Coleta.iniciada_em)))
    if ultima is None:
        return []  # instalação nova, ainda sem nenhum ciclo
    limite = timedelta(minutes=3 * settings.intervalo_coleta_min)
    if ref - ultima > limite:
        minutos = int((ref - ultima).total_seconds() // 60)
        return [Problema("worker_parado", "critico", f"Nenhum ciclo do worker há {minutos} min.")]
    return []


def _coleta(s: Session, settings: Settings, fonte: str, ref: datetime) -> list[Problema]:
    problemas = []
    ultimas = s.execute(
        select(Coleta.erro)
        .where(Coleta.fonte == fonte, Coleta.finalizada_em.is_not(None))
        .order_by(Coleta.id.desc())
        .limit(FALHAS_SEGUIDAS_PARA_ALARME)
    ).all()
    if len(ultimas) == FALHAS_SEGUIDAS_PARA_ALARME and all(erro for (erro,) in ultimas):
        problemas.append(
            Problema(
                f"coleta_falhando:{fonte}",
                "critico",
                f"As últimas {FALHAS_SEGUIDAS_PARA_ALARME} coletas de {fonte.upper()} falharam. "
                f"Último erro: {ultimas[0][0][:300]}",
            )
        )

    if fonte not in FONTES_DIARIOS:
        return problemas  # banca sem documento novo no dia é normal
    local = ref.astimezone(FUSO)
    dia_util = local.weekday() < 5
    if dia_util and local.hour >= settings.alarme_hora_limite_coleta:
        coletas_hoje, lidos_hoje = s.execute(
            select(func.count(), func.coalesce(func.sum(Coleta.itens_lidos), 0)).where(
                Coleta.fonte == fonte,
                Coleta.data_ref == local.date(),
                Coleta.finalizada_em.is_not(None),
                Coleta.erro.is_(None),
            )
        ).one()
        if coletas_hoje and not lidos_hoje:
            problemas.append(
                Problema(
                    f"coleta_zerada:{fonte}",
                    "aviso",
                    f"{fonte.upper()} sem nenhuma publicação candidata hoje ({local:%d/%m}) até as "
                    f"{local:%H:%M}. Pode ser feriado, ou o site mudou de formato.",
                )
            )
    return problemas


def _filas(s: Session, ref: datetime) -> list[Problema]:
    problemas = []
    pendentes_antigas = s.scalar(
        select(func.count())
        .select_from(Publicacao)
        .where(Publicacao.status == "pendente", Publicacao.coletada_em < ref - FILA_PARADA_APOS)
    )
    if pendentes_antigas:
        problemas.append(
            Problema(
                "fila_parada",
                "critico",
                f"{pendentes_antigas} publicações aguardando extração há mais de "
                f"{int(FILA_PARADA_APOS.total_seconds() // 60)} min (API da Anthropic fora? chave inválida?).",
            )
        )

    erros_24h = s.scalar(
        select(func.count())
        .select_from(Publicacao)
        .where(Publicacao.status == "erro", Publicacao.coletada_em > ref - timedelta(hours=24))
    )
    if erros_24h >= ERROS_DE_EXTRACAO_EM_24H:
        problemas.append(
            Problema(
                "extracao_falhando",
                "aviso",
                f"{erros_24h} publicações desistiram da extração nas últimas 24h.",
            )
        )

    alertas_atrasados = s.scalar(
        select(func.count())
        .select_from(Alerta)
        .where(Alerta.status == "pendente", Alerta.criado_em < ref - ENVIO_PARADO_APOS)
    )
    if alertas_atrasados:
        problemas.append(
            Problema(
                "envio_parado",
                "critico",
                f"{alertas_atrasados} alertas esperando envio há mais de "
                f"{int(ENVIO_PARADO_APOS.total_seconds() // 60)} min (token do Telegram?).",
            )
        )
    return problemas
