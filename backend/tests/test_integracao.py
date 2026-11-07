"""Fluxo completo contra um Postgres de verdade (banco separado: radar_test).

Roda com: docker compose run --rm api pytest (fixtures em conftest.py).
"""

import json
from datetime import date, timedelta

import httpx
from sqlalchemy import select

from radar import db
from radar.config import get_settings
from radar.models import Acompanhamento, Alerta, Edital, Publicacao, Usuario
from radar.notify.telegram import Telegram, enviar_pendentes
from radar.pipeline.processor import processar_pendentes
from tests.fakes import ClienteAnthropicFalso, ExtratorFalso, criar_usuario, extraido_exemplo, publicar
from tests.fixtures.textos import EDITAL_ABERTURA, PREGAO, RETIFICACAO


def test_fluxo_completo_abertura_e_retificacao(limpo):
    hoje = date.today()
    fim = (hoje + timedelta(days=20)).isoformat()
    ti = criar_usuario(111, palavras="analista ti", ufs=["DF"])
    criar_usuario(222, palavras="enfermeiro", ufs=["DF"])  # não deve receber
    criar_usuario(333, palavras="professor", ufs=["SP"])  # UF errada

    publicar("1", "EDITAL NORMATIVO Nº 1 – SEEDF", EDITAL_ABERTURA)
    publicar("2", "AVISO DE LICITAÇÃO", PREGAO)
    publicar("1", "duplicada", EDITAL_ABERTURA)  # ignorada (mesmo id externo)

    abertura = extraido_exemplo(
        orgao="Secretaria de Estado de Educação do DF",
        inscricao_fim=fim,
        cargos=[
            {
                "nome": "Analista de Gestão Educacional - Tecnologia da Informação",
                "escolaridade": "superior",
                "vagas": 20,
                "cadastro_reserva": True,
                "salario": 7850,
            },
            {
                "nome": "Professor",
                "escolaridade": "superior",
                "vagas": 100,
                "cadastro_reserva": True,
                "salario": 5800,
            },
        ],
    )
    extrator = ExtratorFalso({"EDITAL NORMATIVO Nº 1 – SEEDF": abertura})
    assert processar_pendentes(extrator, max_tentativas=3) == 2

    with db.session_scope() as s:
        status = dict(s.execute(select(Publicacao.id_externo, Publicacao.status)).all())
        assert status == {"1": "processada", "2": "descartada"}
        edital = s.scalar(select(Edital))
        assert edital.salario_max == 7850
        assert edital.vagas_total == 120
        alertas = s.scalars(select(Alerta)).all()
        assert [(a.usuario_id, a.motivo) for a in alertas] == [(ti, "novo_edital")]
        s.add(Acompanhamento(usuario_id=ti, edital_id=edital.id))
        edital_id = edital.id

    # Envio pelo Telegram (API falsa)
    enviados_para = []

    def telegram_api(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        enviados_para.append(corpo["chat_id"])
        assert "Tecnologia da Informação" in corpo["text"]
        assert corpo["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"acompanhar:{edital_id}"
        return httpx.Response(200, json={"ok": True})

    tg = Telegram("TOKEN", client=httpx.Client(transport=httpx.MockTransport(telegram_api)))
    assert enviar_pendentes(tg, max_tentativas=3) == 1
    assert enviados_para == [111]
    assert enviar_pendentes(tg, max_tentativas=3) == 0  # nada duplicado

    # Retificação chega e vai só para quem acompanha
    publicar("3", "EDITAL Nº 3 – SEEDF", RETIFICACAO)
    retificacao = extraido_exemplo(
        tipo="retificacao",
        orgao="Secretaria de Estado de Educação do DF",
        numero_edital="Edital nº 3/2026",
        edital_referenciado="Edital Normativo nº 1/2026",
        cargos=[],
    )
    processar_pendentes(ExtratorFalso({"EDITAL Nº 3 – SEEDF": retificacao}), max_tentativas=3)
    with db.session_scope() as s:
        ret = s.scalar(select(Edital).where(Edital.tipo == "retificacao"))
        assert ret.edital_pai_id == edital_id
        motivos = s.execute(select(Alerta.usuario_id, Alerta.motivo).where(Alerta.edital_id == ret.id)).all()
        assert motivos == [(ti, "retificacao")]


def test_usuario_que_bloqueou_o_bot_e_desativado(limpo):
    uid = criar_usuario(999, palavras="")
    publicar("10", "EDITAL NORMATIVO Nº 1 – SEEDF", EDITAL_ABERTURA)
    processar_pendentes(
        ExtratorFalso({"EDITAL NORMATIVO Nº 1 – SEEDF": extraido_exemplo(inscricao_fim=None)}), 3
    )

    tg = Telegram(
        "T", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, text="blocked")))
    )
    assert enviar_pendentes(tg, max_tentativas=3) == 0
    with db.session_scope() as s:
        usuario = s.get(Usuario, uid)
        assert usuario.ativo is False
        assert usuario.desativado_em is not None  # inicia o prazo de retenção
        assert s.scalar(select(Alerta.status)) == "erro"


def test_erro_de_extracao_volta_para_fila_e_desiste_depois(limpo):
    from radar.pipeline.extractor import Extrator

    publicar("20", "EDITAL NORMATIVO Nº 1 – SEEDF", EDITAL_ABERTURA)
    extrator = Extrator(get_settings(), client=ClienteAnthropicFalso(stop_reason="refusal"))
    for _ in range(3):
        processar_pendentes(extrator, max_tentativas=3)
    with db.session_scope() as s:
        pub = s.scalar(select(Publicacao))
        assert (pub.status, pub.tentativas) == ("erro", 3)
