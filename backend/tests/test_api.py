from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from radar.api.main import app
from radar.pipeline.processor import processar_pendentes
from tests.fakes import ExtratorFalso, criar_usuario, extraido_exemplo, publicar
from tests.fixtures.textos import EDITAL_ABERTURA

TITULO = "EDITAL NORMATIVO Nº 1 – SEEDF"


@pytest.fixture
def api(limpo):
    return TestClient(app)


@pytest.fixture
def edital_publicado(limpo):
    fim = (date.today() + timedelta(days=10)).isoformat()
    criar_usuario(1, palavras="professor")
    publicar("1", TITULO, EDITAL_ABERTURA)
    processar_pendentes(ExtratorFalso({TITULO: extraido_exemplo(inscricao_fim=fim)}), max_tentativas=3)


def test_health(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_busca_textual_em_portugues_sem_acento(api, edital_publicado):
    resultado = api.get("/editais", params={"q": "seedf"}).json()
    assert [e["titulo"] for e in resultado] == ["Concurso SEEDF 2026"]
    assert resultado[0]["fonte"] == "dodf"
    assert api.get("/editais", params={"q": "policia"}).json() == []


def test_filtro_por_uf_inclui_editais_nacionais(api, edital_publicado):
    assert len(api.get("/editais", params={"uf": "df", "abertos": True}).json()) == 1
    assert api.get("/editais", params={"uf": "SP"}).json() == []


def test_detalhe_com_cargos(api, edital_publicado):
    edital_id = api.get("/editais").json()[0]["id"]
    detalhe = api.get(f"/editais/{edital_id}").json()
    assert detalhe["banca"] == "Cebraspe"
    assert [c["nome"] for c in detalhe["cargos"]] == ["Professor"]
    assert api.get("/editais/999999").status_code == 404


def test_metricas(api, edital_publicado):
    m = api.get("/metricas").json()
    assert m["usuarios_ativos"] == 1
    assert m["editais_de_abertura"] == 1
    assert m["alertas_enviados"] == 0
    assert m["latencia_p50_s"] is None
