"""Diagnóstico de saúde, alarmes com estado e endpoint /saude."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from radar import db
from radar.alarmes import sincronizar
from radar.api.main import app
from radar.config import Settings
from radar.models import Alarme, Alerta, Coleta, Publicacao
from radar.saude import FUSO, Problema, diagnosticar
from tests.fakes import criar_usuario, publicar

# Sexta-feira, 06/11/2026, 11h em Brasília (14h UTC)
SEXTA_11H = datetime(2026, 11, 6, 14, 0, tzinfo=UTC)
SABADO_11H = SEXTA_11H + timedelta(days=1)
SETTINGS = Settings(fontes="dodf", intervalo_coleta_min=10, alarme_hora_limite_coleta=10)


def coleta(*, quando: datetime, lidos: int = 5, erro: str | None = None, dia: date | None = None) -> None:
    with db.session_scope() as s:
        s.add(
            Coleta(
                fonte="dodf",
                data_ref=dia or quando.date(),
                iniciada_em=quando,
                finalizada_em=quando + timedelta(seconds=30),
                itens_lidos=lidos,
                erro=erro,
            )
        )


def chaves(ref: datetime = SEXTA_11H, settings: Settings = SETTINGS) -> dict[str, str]:
    with db.session_scope() as s:
        return {p.chave: p.severidade for p in diagnosticar(s, settings, ref)}


# ------------------------------ diagnóstico ------------------------------
def test_sistema_saudavel(limpo):
    coleta(quando=SEXTA_11H - timedelta(minutes=5))
    assert chaves() == {}


def test_instalacao_nova_sem_coletas_nao_alarma(limpo):
    assert chaves() == {}


def test_worker_parado(limpo):
    coleta(quando=SEXTA_11H - timedelta(minutes=40))
    assert chaves() == {"worker_parado": "critico"}


def test_tres_coletas_seguidas_com_erro(limpo):
    for minutos in (25, 15, 5):
        coleta(quando=SEXTA_11H - timedelta(minutes=minutos), lidos=0, erro="HTTP 500")
    assert chaves()["coleta_falhando:dodf"] == "critico"


def test_erro_isolado_nao_alarma(limpo):
    coleta(quando=SEXTA_11H - timedelta(minutes=25), lidos=0, erro="timeout")
    coleta(quando=SEXTA_11H - timedelta(minutes=15))
    coleta(quando=SEXTA_11H - timedelta(minutes=5), lidos=0, erro="timeout")
    assert "coleta_falhando:dodf" not in chaves()


@pytest.mark.parametrize(
    ("ref", "lidos", "esperado"),
    [
        (SEXTA_11H, 0, True),  # dia útil, depois das 10h, nada lido
        (SEXTA_11H, 3, False),  # leu algo
        (SEXTA_11H - timedelta(hours=2), 0, False),  # 9h: ainda cedo
        (SABADO_11H, 0, False),  # fim de semana não tem edição
    ],
)
def test_coleta_zerada(limpo, ref, lidos, esperado):
    coleta(quando=ref - timedelta(minutes=5), lidos=lidos, dia=ref.astimezone(FUSO).date())
    assert ("coleta_zerada:dodf" in chaves(ref)) is esperado


def test_fila_parada_e_envio_parado(limpo):
    coleta(quando=SEXTA_11H - timedelta(minutes=5))
    uid = criar_usuario(1)
    publicar("1", "EDITAL", "concurso público")
    with db.session_scope() as s:
        pub = s.scalar(select(Publicacao))
        pub.coletada_em = SEXTA_11H - timedelta(hours=2)
    _edital_com_alerta_antigo(uid)
    assert chaves() == {"fila_parada": "critico", "envio_parado": "critico"}


def test_muitos_erros_de_extracao(limpo):
    coleta(quando=SEXTA_11H - timedelta(minutes=5))
    for i in range(5):
        publicar(str(i), "EDITAL", "concurso público")
    with db.session_scope() as s:
        for pub in s.scalars(select(Publicacao)):
            pub.status, pub.coletada_em = "erro", SEXTA_11H - timedelta(hours=3)
    assert chaves() == {"extracao_falhando": "aviso"}


def _edital_com_alerta_antigo(usuario_id: int) -> None:
    from radar.models import Edital

    with db.session_scope() as s:
        pub_id = s.scalar(select(Publicacao.id))
        edital = Edital(publicacao_id=pub_id, tipo="abertura", dados={})
        s.add(edital)
        s.flush()
        s.add(
            Alerta(
                usuario_id=usuario_id,
                edital_id=edital.id,
                motivo="novo_edital",
                criado_em=SEXTA_11H - timedelta(hours=1),
            )
        )


# ------------------------------ alarmes com estado ------------------------------
CRITICO = Problema("fila_parada", "critico", "3 publicações paradas")


def test_alarme_avisa_ao_abrir_e_ao_resolver_sem_repetir(limpo):
    enviados: list[str] = []

    sincronizar([CRITICO], enviados.append, SEXTA_11H)
    sincronizar([CRITICO], enviados.append, SEXTA_11H + timedelta(minutes=10))  # continua: sem novo aviso
    mudancas = sincronizar([], enviados.append, SEXTA_11H + timedelta(minutes=95))

    assert len(enviados) == 2
    assert enviados[0].startswith("🚨 <b>fila_parada</b>")
    assert enviados[1] == "✅ <b>fila_parada</b> resolvido (durou 1h35)."
    assert [c for c, _ in mudancas.resolvidos] == ["fila_parada"]


def test_alarme_reaberto_vira_novo_registro(limpo):
    sincronizar([CRITICO], None, SEXTA_11H)
    sincronizar([], None, SEXTA_11H + timedelta(minutes=10))
    sincronizar([CRITICO], None, SEXTA_11H + timedelta(minutes=20))
    with db.session_scope() as s:
        historico = s.execute(select(Alarme.chave, Alarme.resolvido_em.is_(None)).order_by(Alarme.id)).all()
    assert historico == [("fila_parada", False), ("fila_parada", True)]


def test_falha_ao_notificar_nao_perde_o_estado(limpo):
    def quebrado(_texto):
        raise RuntimeError("Telegram fora do ar")

    sincronizar([CRITICO], quebrado, SEXTA_11H)
    with db.session_scope() as s:
        assert s.scalar(select(Alarme.chave)) == "fila_parada"


# ------------------------------ endpoint /saude ------------------------------
def test_endpoint_saude(limpo):
    cliente = TestClient(app)
    resposta = cliente.get("/saude")
    assert (resposta.status_code, resposta.json()["status"]) == (200, "ok")

    coleta(quando=datetime.now(UTC) - timedelta(hours=5))  # worker parado há horas
    resposta = cliente.get("/saude")
    assert resposta.status_code == 503
    assert resposta.json()["problemas"][0]["chave"] == "worker_parado"


def test_saude_inclui_alarme_aberto_pelo_worker(limpo):
    """Falha de etapa só o worker detecta; o /saude precisa refleti-la mesmo assim."""
    sincronizar([Problema("etapa_falhou:processar", "critico", "sem chave da API")], None)
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 503
    assert [p["chave"] for p in resposta.json()["problemas"]] == ["etapa_falhou:processar"]
