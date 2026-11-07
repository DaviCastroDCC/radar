import io
import json
import zipfile
from datetime import date
from pathlib import Path

import httpx

from radar.collectors.dodf import ColetorDODF, extrair_texto_materia, timestamp_do_dia
from radar.collectors.dou_inlabs import ColetorDOU, artigos_do_zip, parse_artigo_xml
from radar.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
SETTINGS = Settings(pausa_entre_requisicoes_s=0, inlabs_email="a@b.c", inlabs_password="x")

PAGINA_MATERIA = """<html><body><main>
<div class="row conteudo-materia"><div class="col">
<p><p style="text-align:justify;">EDITAL NORMATIVO Nº 1 – SEEDF</p></p>
<p><p>CONCURSO PÚBLICO para provimento de cargos de Professor. Torna pública a abertura de inscrições.</p></p>
</div></div></main></body></html>"""

XML_DOU = """<xml><article id="555" name="Edital 1" idOficio="1" pubName="DO3" artType="Edital"
 pubDate="06/11/2026" artCategory="Ministério da Educação/Universidade Federal de Brasília"
 pdfPage="http://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=06/11/2026&amp;jornal=530&amp;pagina=80"
 idMateria="22334455"><body>
<Identifica><![CDATA[EDITAL Nº 12, DE 5 DE NOVEMBRO DE 2026]]></Identifica>
<Ementa><![CDATA[]]></Ementa>
<Texto><![CDATA[<p class="identifica">EDITAL Nº 12</p><p>A UnB torna pública a abertura de inscrições do concurso público
para o cargo de Professor Adjunto.</p>]]></Texto>
</body></article></xml>"""


# ------------------------------ DODF ------------------------------
def test_timestamp_do_dia_bate_com_o_site():
    # valor visto no site do DODF para a edição de 06/11/2026
    assert timestamp_do_dia(date(2026, 11, 6)) == 1793934000


def test_extrai_texto_da_pagina_da_materia():
    texto = extrair_texto_materia(PAGINA_MATERIA)
    assert texto.startswith("EDITAL NORMATIVO Nº 1 – SEEDF")
    assert "CONCURSO PÚBLICO" in texto


def test_materia_nao_localizada():
    html = '<div class="conteudo-materia"><p>Matéria não localizada!</p></div>'
    assert extrair_texto_materia(html) is None


def _coletor_dodf_falso(diario: dict) -> tuple[ColetorDODF, list[str]]:
    chamadas: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        chamadas.append(f"{request.method} {request.url.path}")
        if request.url.path == "/dodf/jornal/diario":
            return httpx.Response(200, json=diario)
        return httpx.Response(200, text=PAGINA_MATERIA)

    client = httpx.Client(base_url="https://www.dodf.df.gov.br", transport=httpx.MockTransport(responder))
    return ColetorDODF(SETTINGS, client=client), chamadas


def test_coletor_dodf_so_baixa_candidatas():
    diario = json.loads((FIXTURES / "dodf_diario.json").read_text(encoding="utf-8"))
    coletor, chamadas = _coletor_dodf_falso(diario)

    itens = list(coletor.coletar(date(2026, 11, 6), ja_conhecido=lambda _id: False))

    assert [i.id_externo for i in itens] == ["900001"]  # licitação e adesão a ARP ficam de fora
    item = itens[0]
    assert item.titulo == "EDITAL NORMATIVO Nº 1 – SEEDF, DE 5 DE NOVEMBRO DE 2026"
    assert item.orgao == "Secretaria de Estado de Educação"
    assert "co_data=900001" in item.url
    assert sum(c.startswith("GET") for c in chamadas) == 1


def test_coletor_dodf_pula_ja_conhecidas():
    diario = json.loads((FIXTURES / "dodf_diario.json").read_text(encoding="utf-8"))
    coletor, _ = _coletor_dodf_falso(diario)
    assert list(coletor.coletar(date(2026, 11, 6), ja_conhecido=lambda _id: True)) == []


def test_coletor_dodf_sem_edicao_no_dia():
    diario = json.loads((FIXTURES / "dodf_diario.json").read_text(encoding="utf-8"))
    coletor, _ = _coletor_dodf_falso(diario)  # o site devolve a edição de 06/11
    assert list(coletor.coletar(date(2026, 11, 7), ja_conhecido=lambda _id: False)) == []


# ------------------------------ DOU ------------------------------
def test_parse_xml_do_inlabs():
    artigo = parse_artigo_xml(XML_DOU.encode())
    assert artigo["id_externo"] == "22334455"
    assert artigo["secao"] == "DO3"
    assert artigo["data_publicacao"] == date(2026, 11, 6)
    assert artigo["titulo"] == "EDITAL Nº 12, DE 5 DE NOVEMBRO DE 2026"
    assert "concurso público" in artigo["texto"]
    assert artigo["orgao"].startswith("Ministério da Educação")


def _zip(arquivos: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return buffer.getvalue()


def test_artigos_do_zip_ignora_outros_arquivos():
    conteudo = _zip({"a.xml": XML_DOU, "imagem.jpg": "binario"})
    assert [a["id_externo"] for a in artigos_do_zip(conteudo)] == ["22334455"]


def test_coletor_dou_com_login_e_download():
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/logar.php":
            return httpx.Response(200, headers={"set-cookie": "inlabs_session_cookie=abc; Path=/"})
        secao = request.url.params["dl"].removesuffix(".zip").split("-")[-1]
        if secao == "DO3":
            return httpx.Response(200, content=_zip({"a.xml": XML_DOU}))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(responder))
    itens = list(ColetorDOU(SETTINGS, client=client).coletar(date(2026, 11, 6), lambda _id: False))
    assert len(itens) == 1
    assert itens[0].fonte == "dou"
