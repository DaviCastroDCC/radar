"""Alarmes com estado: avisa quando um problema ABRE e quando RESOLVE, nunca a cada ciclo.

Alarme que repete toda hora é ignorado, e alarme ignorado é pior do que nenhum.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from radar.config import Settings
from radar.db import session_scope
from radar.models import Alarme
from radar.relogio import agora
from radar.saude import Problema

log = logging.getLogger(__name__)

Notificador = Callable[[str], None]

ICONES = {"critico": "🚨", "aviso": "⚠️"}


@dataclass(frozen=True)
class Mudancas:
    abertos: list[Problema]
    resolvidos: list[tuple[str, datetime]]  # (chave, aberto_em)


def sincronizar(
    problemas: Sequence[Problema],
    notificar: Notificador | None = None,
    referencia: datetime | None = None,
) -> Mudancas:
    ref = referencia or agora()
    atuais = {p.chave: p for p in problemas}

    with session_scope() as s:
        abertos = {a.chave: a for a in s.scalars(select(Alarme).where(Alarme.resolvido_em.is_(None)))}
        novos = [p for chave, p in atuais.items() if chave not in abertos]
        for p in novos:
            s.add(Alarme(chave=p.chave, severidade=p.severidade, mensagem=p.mensagem, aberto_em=ref))
        resolvidos = []
        for chave, alarme in abertos.items():
            if chave not in atuais:
                alarme.resolvido_em = ref
                resolvidos.append((chave, alarme.aberto_em))

    # Notifica só depois do commit: se o envio falhar, o estado continua correto.
    for p in novos:
        log.error("alarme aberto: %s", p.mensagem, extra={"alarme": p.chave, "severidade": p.severidade})
        _avisar(notificar, f"{ICONES[p.severidade]} <b>{p.chave}</b>\n{p.mensagem}")
    for chave, aberto_em in resolvidos:
        duracao = _duracao(ref - aberto_em)
        log.info("alarme resolvido após %s", duracao, extra={"alarme": chave})
        _avisar(notificar, f"✅ <b>{chave}</b> resolvido (durou {duracao}).")
    return Mudancas(abertos=novos, resolvidos=resolvidos)


def _avisar(notificar: Notificador | None, texto: str) -> None:
    if notificar is None:
        return
    try:
        notificar(texto)
    except Exception:
        log.exception("falha ao enviar alarme para o admin")


def _duracao(delta) -> str:
    minutos = int(delta.total_seconds() // 60)
    if minutos < 60:
        return f"{minutos} min"
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h{minutos:02d}"


def notificador_telegram(settings: Settings) -> Notificador | None:
    """Envia ao chat do admin; sem ADMIN_CHAT_ID os alarmes ficam só nos logs (nível ERROR)."""
    if not (settings.telegram_bot_token and settings.admin_chat_id):
        return None
    from radar.notify.telegram import Telegram

    telegram = Telegram(settings.telegram_bot_token)
    admin = settings.admin_chat_id
    return lambda texto: telegram.enviar(admin, texto)
