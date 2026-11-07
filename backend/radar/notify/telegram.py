"""Envio de alertas pela Bot API do Telegram."""

import logging
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from radar.db import session_scope
from radar.models import Alerta, Edital, Filtro
from radar.notify.mensagens import mensagem_alerta
from radar.pipeline.matcher import casar
from radar.pipeline.processor import agora, edital_para_info, filtro_para_info

log = logging.getLogger(__name__)

# O Telegram aceita ~30 mensagens/s por bot; ficamos abaixo disso.
PAUSA_ENTRE_ENVIOS_S = 0.05


class ErroEnvio(Exception):
    pass


class UsuarioBloqueouBot(ErroEnvio):
    pass


class Telegram:
    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self.url = f"https://api.telegram.org/bot{token}"
        self.client = client or httpx.Client(timeout=httpx.Timeout(20.0))

    def enviar(self, chat_id: int, texto: str, botoes: list[list[dict[str, str]]] | None = None) -> None:
        corpo: dict[str, Any] = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if botoes:
            corpo["reply_markup"] = {"inline_keyboard": botoes}

        for _ in range(3):
            resposta = self.client.post(f"{self.url}/sendMessage", json=corpo)
            if resposta.status_code == 429:
                espera = resposta.json().get("parameters", {}).get("retry_after", 1)
                time.sleep(float(espera))
                continue
            if resposta.status_code == 403:
                raise UsuarioBloqueouBot(resposta.text)
            if resposta.status_code != 200:
                raise ErroEnvio(f"{resposta.status_code}: {resposta.text[:300]}")
            return
        raise ErroEnvio("limite de envio do Telegram (429) persistente")


def enviar_pendentes(telegram: Telegram, max_tentativas: int, limite: int = 1000) -> int:
    with session_scope() as s:
        ids = list(
            s.scalars(select(Alerta.id).where(Alerta.status == "pendente").order_by(Alerta.id).limit(limite))
        )

    enviados = 0
    for alerta_id in ids:
        with session_scope() as s:
            alerta = s.scalars(
                select(Alerta)
                .where(Alerta.id == alerta_id, Alerta.status == "pendente")
                .options(
                    selectinload(Alerta.edital).selectinload(Edital.cargos),
                    selectinload(Alerta.edital).selectinload(Edital.publicacao),
                    selectinload(Alerta.usuario),
                )
                .with_for_update(skip_locked=True, of=Alerta)
            ).first()
            if alerta is None:
                continue  # outro worker pegou
            if not alerta.usuario.telegram_chat_id or not alerta.usuario.ativo:
                alerta.status, alerta.erro = "erro", "usuário sem Telegram ou inativo"
                continue

            texto, botoes = montar_alerta(s, alerta)
            try:
                telegram.enviar(alerta.usuario.telegram_chat_id, texto, botoes)
            except UsuarioBloqueouBot:
                alerta.usuario.ativo = False
                alerta.status, alerta.erro = "erro", "usuário bloqueou o bot"
                continue
            except (ErroEnvio, httpx.HTTPError) as e:
                alerta.tentativas += 1
                alerta.erro = str(e)[:500]
                if alerta.tentativas >= max_tentativas:
                    alerta.status = "erro"
                log.warning("alerta %s falhou: %s", alerta.id, e)
                continue

            alerta.status = "enviado"
            alerta.enviado_em = agora()
            alerta.erro = None
            enviados += 1
        time.sleep(PAUSA_ENTRE_ENVIOS_S)

    if ids:
        log.info("alertas: %s enviados de %s pendentes", enviados, len(ids))
    return enviados


def montar_alerta(s, alerta: Alerta) -> tuple[str, list[list[dict[str, str]]]]:
    edital = alerta.edital
    cargos_casados: list[str] = []
    if alerta.motivo == "novo_edital":
        info = edital_para_info(edital)
        filtros = s.scalars(select(Filtro).where(Filtro.usuario_id == alerta.usuario_id, Filtro.ativo))
        for filtro in filtros:
            casamento = casar(info, filtro_para_info(filtro))
            if casamento:
                cargos_casados += [c for c in casamento.cargos if c not in cargos_casados]

    texto = mensagem_alerta(
        motivo=alerta.motivo,
        tipo=edital.tipo,
        titulo=edital.titulo,
        orgao=edital.orgao,
        banca=edital.banca,
        uf=edital.uf,
        salario_max=edital.salario_max,
        vagas_total=edital.vagas_total,
        inscricao_inicio=edital.inscricao_inicio,
        inscricao_fim=edital.inscricao_fim,
        data_prova=edital.data_prova,
        link_inscricao=edital.link_inscricao,
        resumo=edital.resumo,
        cargos_casados=cargos_casados,
        fonte=edital.publicacao.fonte,
        data_publicacao=edital.publicacao.data_publicacao,
        url_publicacao=edital.publicacao.url,
    )
    alvo = edital.edital_pai_id or edital.id
    botoes = [[{"text": "🔔 Acompanhar retificações", "callback_data": f"acompanhar:{alvo}"}]]
    return texto, botoes
