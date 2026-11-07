from decimal import Decimal

import pytest

from radar.bot.comandos import parse_filtro


def test_filtro_completo():
    f = parse_filtro("Analista TI; uf=df, go; salario=6.500,00; escolaridade=superior")
    assert f.palavras == "Analista TI"
    assert f.ufs == ["DF", "GO"]
    assert f.salario_min == Decimal("6500.00")
    assert f.escolaridades == ["superior"]


def test_so_palavras():
    f = parse_filtro("policia federal")
    assert f.palavras == "policia federal"
    assert f.ufs == []


def test_salario_sem_centavos_e_escolaridade_com_acento():
    f = parse_filtro("uf=DF; salário=6000; escolaridade=Médio,técnico")
    assert f.salario_min == Decimal("6000")
    assert f.escolaridades == ["medio", "tecnico"]


@pytest.mark.parametrize(
    ("entrada", "erro"),
    [
        ("uf=XX", "UF inválida"),
        ("escolaridade=doutorado", "Escolaridade inválida"),
        ("cor=azul", "Não entendi"),
        ("", "Filtro vazio"),
        ("salario=abc", "Salário inválido"),
    ],
)
def test_entradas_invalidas(entrada, erro):
    with pytest.raises(ValueError, match=erro):
        parse_filtro(entrada)


def test_descricao_escapa_html():
    assert "&lt;b&gt;" in parse_filtro("<b>hack</b>").descricao()
