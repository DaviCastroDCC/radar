"""Coletores de bancas, leitura de documentos e deduplicação entre fontes."""

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from radar import db
from radar.collectors import FONTES_DIARIOS, criar_coletores
from radar.collectors.bancas import documento_relevante
from radar.collectors.bancas.cebraspe import ColetorCebraspe
from radar.config import Settings
from radar.documentos import ErroDocumento, PdfEscaneado, texto_de_documento, texto_de_pdf
from radar.models import Alerta, Edital, Publicacao
from radar.pipeline.processor import coletada_recentemente, coletar_fonte, processar_pendentes
from tests.fakes import ExtratorFalso, criar_usuario, extraido_exemplo, pdf_com_texto, publicar
from tests.fixtures.textos import EDITAL_ABERTURA, RETIFICACAO

SETTINGS = Settings(pausa_entre_requisicoes_s=0)
HOJE = date(2026, 11, 6)
EDITAL_PDF = pdf_com_texto(
    "EDITAL N. 1 - SEAP/PE, DE 3 DE NOVEMBRO DE 2026\n"
    "Secretaria Executiva de Administracao Penitenciaria\n"
    "de Pernambuco - concurso publico",
    "CONCURSO PUBLICO para o cargo de Policial Penal.\n"
    "Torna publica a abertura de inscricoes\n"
    "para provimento de 700 vagas.",
)


# ------------------------------ documentos ------------------------------
def test_texto_de_pdf_de_varias_paginas():
    texto = texto_de_pdf(pdf_com_texto("primeira pagina com texto suficiente " * 3, "segunda pagina " * 6))
    assert "primeira pagina" in texto
    assert "segunda pagina" in texto


def test_pdf_sem_texto_e_identificado_como_escaneado():
    with pytest.raises(PdfEscaneado):
        texto_de_pdf(pdf_com_texto(""))


def test_documento_invalido_ou_desconhecido():
    with pytest.raises(ErroDocumento):
        texto_de_pdf(b"%PDF-isto nao e um pdf")
    with pytest.raises(ErroDocumento):
        texto_de_documento(b"\x00\x01", "application/zip", "a.zip")
    assert texto_de_documento(b"<p>Edital</p>", "text/html") == "Edital"


@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        ("Edital nº 1 - Abertura", True),
        ("Edital nº 2 – Retificação do subitem 10.2", True),
        ("Edital nº 3 - Prorrogação das inscrições", True),
        ("Edital nº 1 - Abertura - em VLibras", False),  # versão acessível duplicada
        ("Edital nº 9 - Resultado final", False),  # lista enorme, cheia de dados pessoais
        ("Edital nº 4 - Retificação do resultado provisório", False),
        ("Edital nº 5 - Convocação para a perícia médica", False),
    ],
)
def test_filtro_de_tipo_de_documento(descricao, esperado):
    assert documento_relevante(descricao) is esperado


# ------------------------------ Cebraspe ------------------------------
def _arquivo(nome: str, descricao: str, quando: date, ext: str = "pdf") -> dict:
    return {
        "tipoExtensaoArquivo": f"_.{ext}",
        "nomeArquivo": f"{nome}.{ext}",
        "descricaoArquivo": descricao,
        "isGuid": False,
        "dataArquivo": quando.strftime("%d/%m/%Y 10:30"),
        "dataArquivoObj": f"{quando.isoformat()}T10:30:00",
    }


LISTA = [
    {"faseEvento": "Novos", "eventos": [{"eventoURL": "SEAP_PE_26"}]},
    {"faseEvento": "Encerrados", "eventos": [{"eventoURL": "ABIN_17"}]},  # nunca deve ser consultado
]
DETALHE = {
    "eventoURL": "SEAP_PE_26",
    "eventoTipo": "concursos",
    "eventoNomeCompleto": "SEAP PE 26",
    "arquivosEdital": [
        _arquivo("abertura", "Edital nº 1 - Abertura", HOJE - timedelta(days=2)),
        _arquivo("abertura-libras", "Edital nº 1 - Abertura - em VLibras", HOJE - timedelta(days=2), "html"),
        _arquivo("resultado", "Edital nº 5 - Resultado final", HOJE),
        _arquivo("antigo", "Edital nº 1 - Abertura", HOJE - timedelta(days=60)),
    ],
}


def _cebraspe() -> tuple[ColetorCebraspe, list[str]]:
    pedidos: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request.url.path)
        if request.url.path.endswith("/eventos/tipo/concursos/"):
            return httpx.Response(200, json=LISTA)
        if request.url.path.endswith("/eventos/SEAP_PE_26"):
            return httpx.Response(200, json=DETALHE)
        if request.url.path.endswith("/abertura.pdf"):
            return httpx.Response(200, content=EDITAL_PDF, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    return ColetorCebraspe(SETTINGS, client=httpx.Client(transport=httpx.MockTransport(responder))), pedidos


def test_cebraspe_baixa_so_documentos_relevantes_e_recentes():
    coletor, pedidos = _cebraspe()
    [pub] = list(coletor.coletar(HOJE, ja_conhecido=lambda _id: False))

    assert pub.fonte == "cebraspe"
    assert pub.id_externo == "SEAP_PE_26/abertura.pdf"
    assert pub.titulo == "Edital nº 1 - Abertura – SEAP PE 26"
    assert pub.data_publicacao == HOJE - timedelta(days=2)
    assert pub.url == "https://cdn.cebraspe.org.br/concursos/SEAP_PE_26/arquivos/abertura.pdf"
    assert "CONCURSO PUBLICO" in pub.texto
    assert not any("ABIN_17" in p for p in pedidos)  # concurso encerrado não é consultado
    assert sum(p.endswith(".pdf") or p.endswith(".html") for p in pedidos) == 1  # só baixou 1 arquivo


def test_cebraspe_nao_baixa_de_novo_o_que_ja_conhece():
    coletor, pedidos = _cebraspe()
    assert list(coletor.coletar(HOJE, ja_conhecido=lambda _id: True)) == []
    assert not any(p.endswith(".pdf") for p in pedidos)


def test_registro_de_fontes():
    fontes = [c.fonte for c in criar_coletores(Settings(fontes="dodf,cebraspe,dodf"))]
    assert fontes == ["dodf", "cebraspe"]  # sem duplicar
    with pytest.raises(ValueError, match="desconhecida"):
        criar_coletores(Settings(fontes="vunesp"))
    assert "cebraspe" not in FONTES_DIARIOS


def test_coleta_de_banca_lembra_da_janela_e_respeita_intervalo(limpo):
    coletor, pedidos = _cebraspe()
    assert coletar_fonte(coletor, HOJE) == (1, 1)
    assert coletada_recentemente("cebraspe", minutos=30)
    assert not coletada_recentemente("dou", minutos=30)

    pedidos.clear()
    assert coletar_fonte(coletor, HOJE) == (0, 0)  # documento de 2 dias atrás já é conhecido
    assert not any(p.endswith(".pdf") for p in pedidos)


# ------------------------------ deduplicação ------------------------------
def test_mesmo_edital_na_banca_e_no_diario_gera_um_alerta_so(limpo):
    fim = (date.today() + timedelta(days=20)).isoformat()
    criar_usuario(1, palavras="professor")
    publicar("banca-1", "BANCA", EDITAL_ABERTURA)
    publicar("dou-1", "DOU", EDITAL_ABERTURA)
    publicar("dou-2", "RETIFICACAO", RETIFICACAO)
    extrator = ExtratorFalso(
        {
            "BANCA": extraido_exemplo(orgao="Secretaria de Estado de Educação do Distrito Federal", inscricao_fim=fim),
            "DOU": extraido_exemplo(orgao="SECRETARIA DE EDUCAÇÃO DO DF", numero_edital="EDITAL Nº 01/2026", inscricao_fim=fim),
            "RETIFICACAO": extraido_exemplo(
                tipo="retificacao", orgao="SEE DF Educação", numero_edital="Edital nº 3/2026",
                edital_referenciado="Edital nº 1/2026", cargos=[],
            ),
        }
    )  # fmt: skip

    processar_pendentes(extrator, max_tentativas=3)

    with db.session_scope() as s:
        original, duplicata, retificacao = s.scalars(select(Edital).order_by(Edital.id)).all()
        assert original.duplicata_de_id is None
        assert duplicata.duplicata_de_id == original.id
        assert retificacao.edital_pai_id == original.id  # liga ao original, não à duplicata
        assert s.scalars(select(Alerta.edital_id)).all() == [original.id]


def test_documento_de_banca_vai_para_a_ia_mesmo_sem_frase_de_concurso(limpo):
    """Retificação curta da banca não repete "concurso público"; no diário, o mesmo texto é descartado."""
    texto = "Torna pública a retificação da data constante do subitem 4.2 do Edital nº 1/2026."
    publicar("banca-ret", "RET BANCA", texto, fonte="cebraspe")
    publicar("dodf-ret", "RET DODF", texto, fonte="dodf")
    retificacao = extraido_exemplo(tipo="retificacao", edital_referenciado="Edital nº 1/2026", cargos=[])

    processar_pendentes(ExtratorFalso({"RET BANCA": retificacao}), max_tentativas=3)

    with db.session_scope() as s:
        status = dict(s.execute(select(Publicacao.fonte, Publicacao.status)).all())
    assert status == {"cebraspe": "processada", "dodf": "descartada"}
