from radar.pipeline.detector import detectar, talvez_concurso
from tests.fixtures.textos import EDITAL_ABERTURA, NOMEACAO, PREGAO, RETIFICACAO


def test_edital_de_abertura_e_candidato():
    d = detectar("EDITAL NORMATIVO Nº 1 – SEEDF", EDITAL_ABERTURA)
    assert d.candidato
    assert not d.parece_retificacao
    assert d.score >= 10


def test_pregao_nao_e_candidato():
    assert not detectar("AVISO DE LICITAÇÃO", PREGAO).candidato


def test_retificacao_curta_passa_com_limiar_menor():
    d = detectar("EDITAL Nº 3 – SEEDF", RETIFICACAO)
    assert d.parece_retificacao
    assert d.candidato


def test_nomeacao_de_aprovados_e_descartada():
    assert not detectar("DECRETO DE 3 DE NOVEMBRO DE 2026", NOMEACAO).candidato


def test_pre_filtro():
    assert talvez_concurso("EDITAL Nº 5, DE 1º DE NOVEMBRO", "")
    assert talvez_concurso("AVISO", "resultado do Concurso Público")
    assert not talvez_concurso("EXTRATO DE CONTRATO", "aquisição de cadeiras")
