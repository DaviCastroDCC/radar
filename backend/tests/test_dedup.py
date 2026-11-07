"""Reconhecer o mesmo concurso vindo de fontes diferentes."""

import pytest

from radar.pipeline.dedup import (
    mesmo_concurso,
    numero_e_ano,
    numeros_compativeis,
    orgaos_parecidos,
    ufs_do_orgao,
)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Edital nº 01/2026", (1, 2026)),
        ("EDITAL NORMATIVO Nº 1 / 2026 – SEEDF", (1, 2026)),
        ("Edital nº 7", (7, None)),
        ("EDITAL Nº 1 – SEAP/PE, DE 3 DE NOVEMBRO DE 2026", (1, 2026)),
        ("sem número", None),
        (None, None),
    ],
)
def test_numero_e_ano(texto, esperado):
    assert numero_e_ano(texto) == esperado


def test_ano_so_conta_quando_os_dois_lados_tem():
    assert numeros_compativeis("Edital nº 1/2026", "Edital nº 1")
    assert numeros_compativeis("Edital nº 1/2026", "EDITAL Nº 01/2026")
    assert not numeros_compativeis("Edital nº 1/2026", "Edital nº 1/2025")
    assert not numeros_compativeis("Edital nº 1/2026", "Edital nº 2/2026")


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ("Polícia Civil de Pernambuco", "POLÍCIA CIVIL DO ESTADO DE PERNAMBUCO", True),
        ("Polícia Civil de Pernambuco", "PC PE", False),  # sigla sem nome: melhor não arriscar
        ("Polícia Civil - PE", "Polícia Civil do Estado de Pernambuco", True),  # UF por extenso
        ("Câmara dos Deputados", "CÂMARA DOS DEPUTADOS", True),
        ("Polícia Civil de Pernambuco", "Polícia Civil da Paraíba", False),
        ("Secretaria de Estado de Saúde do DF", "Secretaria de Estado de Educação do DF", False),
        (None, "Câmara dos Deputados", False),
    ],
)
def test_orgaos_parecidos(a, b, esperado):
    assert orgaos_parecidos(a, b) is esperado


def test_mesmo_concurso_exige_numero_e_orgao():
    assert mesmo_concurso(
        "Polícia Civil de Pernambuco",
        "Edital nº 1/2026",
        "POLÍCIA CIVIL DO ESTADO DE PERNAMBUCO",
        "EDITAL Nº 1",
    )
    assert not mesmo_concurso(
        "Polícia Civil de Pernambuco", "Edital nº 1/2026", "Polícia Civil de Pernambuco", "Edital nº 2/2026"
    )
    assert not mesmo_concurso(
        "Polícia Civil de Pernambuco", "Edital nº 1/2026", "Polícia Civil de Alagoas", "Edital nº 1/2026"
    )


def test_orgao_de_uma_palavra_nao_casa_por_inclusao():
    """Falso positivo aqui junta concursos diferentes e o usuário perde um alerta."""
    assert not orgaos_parecidos("Educação", "Secretaria de Educação de Goiás")


@pytest.mark.parametrize(
    ("orgao", "ufs"),
    [
        ("Polícia Civil do Estado de Pernambuco", {"pe"}),
        ("SECRETARIA DE EDUCAÇÃO DO DF", {"df"}),
        ("Tribunal de Justiça de Mato Grosso do Sul", {"ms"}),  # não confunde com Mato Grosso
        ("Universidade Federal do Pará", {"pa"}),
        ("Secretaria para Assuntos Estratégicos", set()),  # "para" é preposição, não o Pará
        ("Câmara dos Deputados", set()),
    ],
)
def test_ufs_do_orgao(orgao, ufs):
    assert ufs_do_orgao(orgao) == ufs
