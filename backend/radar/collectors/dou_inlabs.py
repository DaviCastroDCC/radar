"""Coletor do Diário Oficial da União via INLABS (Imprensa Nacional).

O INLABS entrega cada seção do DOU do dia como um .zip de arquivos XML, um por
matéria. Precisa de login gratuito em https://inlabs.in.gov.br. Fluxo baseado no
script oficial: https://github.com/Imprensa-Nacional/inlabs
"""

import io
import logging
import time
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

import httpx
from lxml import etree

from radar.collectors.base import ErroColeta, JaConhecido, PublicacaoColetada
from radar.config import Settings
from radar.pipeline.detector import talvez_concurso
from radar.texto import html_para_texto

log = logging.getLogger(__name__)

URL_LOGIN = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD = "https://inlabs.in.gov.br/index.php"
COOKIE_SESSAO = "inlabs_session_cookie"


def _texto_do_no(artigo: Any, tag: str) -> str:
    no = artigo.find(f".//{tag}")
    return (no.text or "").strip() if no is not None else ""


def parse_artigo_xml(conteudo: bytes) -> dict[str, Any] | None:
    """Converte um XML de matéria do INLABS em dicionário. Devolve None se não for uma matéria."""
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    raiz = etree.fromstring(conteudo, parser=parser)
    if raiz is None:
        return None
    artigo = raiz if raiz.tag == "article" else raiz.find(".//article")
    if artigo is None:
        return None

    atributos = dict(artigo.attrib)
    texto_html = _texto_do_no(artigo, "Texto")
    data_txt = atributos.get("pubDate", "")
    try:
        data_pub = datetime.strptime(data_txt, "%d/%m/%Y").date()
    except ValueError:
        data_pub = None

    return {
        "id_externo": atributos.get("idMateria") or atributos.get("id"),
        "secao": atributos.get("pubName"),
        "tipo_ato": atributos.get("artType"),
        "orgao": atributos.get("artCategory"),
        "url": atributos.get("pdfPage"),
        "data_publicacao": data_pub,
        "titulo": _texto_do_no(artigo, "Identifica") or atributos.get("name"),
        "texto": html_para_texto(texto_html),
    }


def artigos_do_zip(conteudo_zip: bytes) -> Iterator[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as arquivo:
        for nome in arquivo.namelist():
            if not nome.lower().endswith(".xml"):
                continue
            try:
                artigo = parse_artigo_xml(arquivo.read(nome))
            except etree.XMLSyntaxError:
                log.warning("DOU: XML inválido em %s", nome)
                continue
            if artigo and artigo["id_externo"]:
                yield artigo


class ColetorDOU:
    fonte = "dou"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.email = settings.inlabs_email
        self.senha = settings.inlabs_password
        self.secoes = [s.strip() for s in settings.dou_secoes.split(",") if s.strip()]
        self.pausa = settings.pausa_entre_requisicoes_s
        self.client = client or httpx.Client(
            headers={"User-Agent": settings.http_user_agent},
            timeout=httpx.Timeout(120.0),
            follow_redirects=True,
        )

    def _login(self) -> None:
        if not (self.email and self.senha):
            raise ErroColeta("INLABS_EMAIL/INLABS_PASSWORD não configurados")
        self.client.post(
            URL_LOGIN,
            data={"email": self.email, "password": self.senha},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not self.client.cookies.get(COOKIE_SESSAO):
            raise ErroColeta("Login no INLABS falhou: verifique e-mail e senha")

    def baixar_secao(self, dia: date, secao: str) -> bytes | None:
        data_iso = dia.isoformat()
        resposta = self.client.get(
            URL_DOWNLOAD,
            params={"p": data_iso, "dl": f"{data_iso}-{secao}.zip"},
            headers={"origem": "736372697074"},  # cabeçalho usado pelo script oficial
        )
        time.sleep(self.pausa)
        if resposta.status_code == 404:
            return None
        resposta.raise_for_status()
        if not resposta.content.startswith(b"PK"):
            # Seção ainda não publicada (ou sessão expirada): o INLABS devolve HTML.
            return None
        return resposta.content

    def coletar(self, dia: date, ja_conhecido: JaConhecido) -> Iterator[PublicacaoColetada]:
        self._login()
        for secao in self.secoes:
            conteudo = self.baixar_secao(dia, secao)
            if conteudo is None:
                log.info("DOU %s %s ainda não disponível", dia, secao)
                continue
            for artigo in artigos_do_zip(conteudo):
                if ja_conhecido(artigo["id_externo"]):
                    continue
                if not talvez_concurso(artigo["titulo"] or "", artigo["texto"]):
                    continue
                yield PublicacaoColetada(
                    fonte=self.fonte,
                    id_externo=artigo["id_externo"],
                    data_publicacao=artigo["data_publicacao"] or dia,
                    texto=artigo["texto"],
                    titulo=artigo["titulo"],
                    secao=artigo["secao"],
                    orgao=artigo["orgao"],
                    tipo_ato=artigo["tipo_ato"],
                    url=artigo["url"],
                )
