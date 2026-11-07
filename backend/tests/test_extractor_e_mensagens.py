from datetime import date
from decimal import Decimal

import pytest

from radar.config import Settings
from radar.notify.mensagens import mensagem_alerta, reais
from radar.pipeline.extractor import EditalExtraido, ErroExtracao, Extrator, parse_data
from tests.fakes import ClienteAnthropicFalso, extraido_exemplo


def test_extrator_envia_modelo_esforco_e_schema():
    cliente = ClienteAnthropicFalso(parsed=extraido_exemplo())
    extrator = Extrator(Settings(extractor_model="claude-haiku-5-5", extractor_effort="low"), client=cliente)
    resultado = extrator.extrair(
        fonte="dodf", data=date(2026, 11, 6), orgao="SEEDF", titulo="EDITAL", texto="..."
    )
    assert resultado.banca == "Cebraspe"
    kw = cliente.chamadas[0]
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["output_config"] == {"effort": "low"}
    assert kw["output_format"] is EditalExtraido


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_extrator_trata_paradas_anormais(stop_reason):
    extrator = Extrator(
        Settings(), client=ClienteAnthropicFalso(stop_reason=stop_reason, parsed=extraido_exemplo())
    )
    with pytest.raises(ErroExtracao):
        extrator.extrair(fonte="dou", data=date(2026, 11, 6), orgao=None, titulo=None, texto="x")


def test_parse_data():
    assert parse_data("2026-11-30") == date(2026, 11, 30)
    assert parse_data("30/11/2026") is None
    assert parse_data(None) is None


def test_reais():
    assert reais(Decimal("7850")) == "R$ 7.850,00"
    assert reais(12345.6) == "R$ 12.345,60"


def test_mensagem_de_alerta():
    texto = mensagem_alerta(
        motivo="novo_edital",
        tipo="abertura",
        titulo="Concurso <SEEDF>",
        orgao="SEEDF",
        banca="Cebraspe",
        uf="DF",
        salario_max=Decimal("7850"),
        vagas_total=120,
        inscricao_inicio=date(2026, 11, 10),
        inscricao_fim=date(2026, 11, 30),
        data_prova=None,
        link_inscricao=None,
        resumo="Resumo.",
        cargos_casados=["Analista TI"],
        fonte="dodf",
        data_publicacao=date(2026, 11, 6),
        url_publicacao="https://www.dodf.df.gov.br/x?a=1&b=2",
    )
    assert "Concurso &lt;SEEDF&gt;" in texto
    assert "Até R$ 7.850,00" in texto
    assert "Inscrições: 10/11/2026 a 30/11/2026" in texto
    assert 'href="https://www.dodf.df.gov.br/x?a=1&amp;b=2"' in texto
