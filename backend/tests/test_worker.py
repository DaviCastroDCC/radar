"""Orquestração do worker e configuração de logs."""

import json
import logging
from datetime import date

from sqlalchemy import select

from radar import db, worker
from radar.logs import FormatoJson, FormatoTexto
from radar.models import Alarme


def test_etapa_que_falha_nao_impede_as_seguintes():
    executadas = []

    def quebra():
        raise RuntimeError("API fora")

    falhas = worker.executar_etapas(
        [("a", lambda: executadas.append("a")), ("b", quebra), ("c", lambda: executadas.append("c"))]
    )

    assert executadas == ["a", "c"]
    assert [(f.chave, f.severidade) for f in falhas] == [("etapa_falhou:b", "critico")]
    assert "RuntimeError: API fora" in falhas[0].mensagem


def test_ciclo_transforma_falha_em_alarme_e_avisa_o_admin(limpo, monkeypatch):
    avisos: list[str] = []
    monkeypatch.setattr(worker, "notificador_telegram", lambda _settings: avisos.append)

    def quebra():
        raise ConnectionError("sem rede")

    monkeypatch.setattr(worker, "ETAPAS", [("coletar", quebra), ("notificar", lambda: None)])
    worker.ciclo()
    worker.ciclo()  # segundo ciclo com o mesmo problema: sem aviso repetido

    with db.session_scope() as s:
        assert s.scalars(select(Alarme.chave)).all() == ["etapa_falhou:coletar"]
    assert len(avisos) == 1

    monkeypatch.setattr(worker, "ETAPAS", [("coletar", lambda: None)])
    worker.ciclo()
    assert avisos[-1].startswith("✅ <b>etapa_falhou:coletar</b> resolvido")


def test_coletar_filtra_por_fonte(monkeypatch):
    class Coletor:
        def __init__(self, fonte):
            self.fonte = fonte

    chamadas = []
    monkeypatch.setattr(worker, "criar_coletores", lambda _s: [Coletor("dodf"), Coletor("dou")])
    monkeypatch.setattr(worker, "coletar_fonte", lambda c, dia: chamadas.append((c.fonte, dia)))

    worker.coletar("dou", date(2026, 11, 6))
    assert chamadas == [("dou", date(2026, 11, 6))]


def test_cli_despacha_comandos(monkeypatch):
    chamados = []
    monkeypatch.setattr(worker, "processar", lambda: chamados.append("processar"))
    monkeypatch.setattr(worker, "coletar", lambda fonte, dia: chamados.append(("coletar", fonte, dia)))
    monkeypatch.setattr(worker, "configurar_logs", lambda *_: None)

    worker.main(["processar"])
    worker.main(["coletar", "--fonte", "dodf", "--data", "2026-11-06"])
    assert chamados == ["processar", ("coletar", "dodf", date(2026, 11, 6))]


def test_notificar_sem_token_nao_quebra(monkeypatch, caplog):
    monkeypatch.setattr(worker.get_settings(), "telegram_bot_token", None)
    with caplog.at_level(logging.WARNING):
        worker.notificar()
    assert "TELEGRAM_BOT_TOKEN" in caplog.text


# ------------------------------ logs ------------------------------
def _registro(**extra) -> logging.LogRecord:
    registro = logging.LogRecord("radar.teste", logging.INFO, __file__, 1, "coleta %s", ("ok",), None)
    registro.__dict__.update(extra)
    return registro


def test_log_json_tem_campos_extras():
    evento = json.loads(FormatoJson().format(_registro(fonte="dodf", novas=3, dia=date(2026, 11, 6))))
    assert evento["msg"] == "coleta ok"
    assert evento["nivel"] == "INFO"
    assert (evento["fonte"], evento["novas"], evento["dia"]) == ("dodf", 3, "2026-11-06")


def test_log_json_inclui_excecao():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        registro = logging.LogRecord("radar", logging.ERROR, __file__, 1, "falhou", (), sys.exc_info())
    assert "ValueError: boom" in json.loads(FormatoJson().format(registro))["exc"]


def test_log_texto_mostra_extras_no_fim():
    assert FormatoTexto().format(_registro(fonte="dou")).endswith("coleta ok  fonte=dou")
