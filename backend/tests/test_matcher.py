from decimal import Decimal

from radar.pipeline.matcher import CargoInfo, EditalInfo, FiltroInfo, casar, termos_do_filtro

EDITAL = EditalInfo(
    titulo="Concurso SEEDF 2026",
    orgao="Secretaria de Estado de Educação do Distrito Federal",
    uf="DF",
    cargos=[
        CargoInfo("Analista de Gestão Educacional - Tecnologia da Informação", "superior", Decimal("7850")),
        CargoInfo("Professor de Educação Básica", "superior", Decimal("5800")),
        CargoInfo("Monitor de Gestão Educacional", "medio", Decimal("3100")),
    ],
)


def test_sigla_expande_para_sinonimo():
    assert termos_do_filtro("Analista TI") == [
        ["analista"],
        ["ti", "tecnologia da informacao", "informatica"],
    ]


def test_casa_cargo_por_sigla_e_sem_acento():
    r = casar(EDITAL, FiltroInfo(palavras="analista ti", ufs=["DF"]))
    assert r
    assert r.cargos == ["Analista de Gestão Educacional - Tecnologia da Informação"]


def test_uf_diferente_nao_casa():
    assert casar(EDITAL, FiltroInfo(palavras="professor", ufs=["GO"])) is None


def test_edital_nacional_casa_com_qualquer_uf():
    nacional = EditalInfo(
        titulo="Concurso INSS",
        orgao="INSS",
        uf="BR",
        cargos=[CargoInfo("Técnico do Seguro Social", "medio", 5900)],
    )
    assert casar(nacional, FiltroInfo(palavras="tecnico", ufs=["GO"]))


def test_salario_minimo():
    r = casar(EDITAL, FiltroInfo(salario_min=Decimal("5000")))
    assert r
    assert set(r.cargos) == {
        "Analista de Gestão Educacional - Tecnologia da Informação",
        "Professor de Educação Básica",
    }


def test_escolaridade():
    r = casar(EDITAL, FiltroInfo(escolaridades=["medio"]))
    assert r
    assert r.cargos == ["Monitor de Gestão Educacional"]


def test_plural_no_filtro_casa_com_singular():
    assert casar(EDITAL, FiltroInfo(palavras="professores"))
    assert casar(EDITAL, FiltroInfo(palavras="analistas ti"))
    assert termos_do_filtro("vagas") == [["vagas", "vaga"]]


def test_palavra_pelo_orgao():
    r = casar(EDITAL, FiltroInfo(palavras="educação"))
    assert r
    assert len(r.cargos) == 3


def test_edital_sem_cargos_usa_titulo_e_resumo():
    sem_cargos = EditalInfo(
        titulo="Processo seletivo PCDF", orgao="Polícia Civil do DF", uf="DF", resumo="Vagas para agente"
    )
    assert casar(sem_cargos, FiltroInfo(palavras="agente"))
    assert casar(sem_cargos, FiltroInfo(palavras="escrivão")) is None


def test_sigla_curta_nao_casa_dentro_de_palavra():
    edital = EditalInfo(
        titulo="Concurso", orgao="Prefeitura", uf="GO", cargos=[CargoInfo("Técnico em Tipografia", "medio")]
    )
    assert casar(edital, FiltroInfo(palavras="ti")) is None
