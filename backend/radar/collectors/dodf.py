"""Coletor do Diário Oficial do Distrito Federal (https://www.dodf.df.gov.br).

O site carrega o diário por AJAX: POST /dodf/jornal/diario devolve JSON com as
matérias do dia (10 por página, com um trecho do texto). O texto completo de cada
matéria fica em /dodf/materia/visualizar, dentro de .conteudo-materia.
"""

import html
import logging
import time
from collections.abc import Iterator
from datetime import date, datetime
from datetime import time as dtime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from radar.collectors.base import ErroColeta, JaConhecido, PublicacaoColetada
from radar.config import Settings
from radar.pipeline.detector import talvez_concurso
from radar.texto import html_para_texto

log = logging.getLogger(__name__)

BASE_URL = "https://www.dodf.df.gov.br"
FUSO = ZoneInfo("America/Sao_Paulo")


def timestamp_do_dia(dia: date) -> int:
    """O DODF identifica cada edição pela meia-noite (horário de Brasília) em epoch."""
    return int(datetime.combine(dia, dtime(0), FUSO).timestamp())


def url_materia(materia: dict[str, Any]) -> str:
    return f"{BASE_URL}/dodf/materia/visualizar?co_data={materia['coMateria']}&p={materia.get('slug') or ''}"


def orgao_da_materia(materia: dict[str, Any]) -> str | None:
    poder = materia.get("poder")
    if isinstance(poder, list):
        return " / ".join(p for p in poder if p) or None
    return poder or None


def extrair_texto_materia(pagina_html: str) -> str | None:
    soup = BeautifulSoup(pagina_html, "lxml")
    conteudo = soup.select_one(".conteudo-materia")
    if conteudo is None:
        return None
    texto = html_para_texto(str(conteudo))
    if not texto or "Matéria não localizada" in texto:
        return None
    return texto


class ColetorDODF:
    fonte = "dodf"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.pausa = settings.pausa_entre_requisicoes_s
        self.client = client or httpx.Client(
            base_url=BASE_URL,
            headers={"User-Agent": settings.http_user_agent},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    def _pagina_do_diario(self, ts: int, pagina: int, tp_jornal: str, letra: str) -> dict[str, Any]:
        resposta = self.client.post(
            "/dodf/jornal/diario",
            data={"data": ts, "pagina": pagina, "tpJornal": tp_jornal, "letra": letra},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        resposta.raise_for_status()
        dados = resposta.json()
        if dados.get("type") != "success":
            raise ErroColeta(f"DODF respondeu {dados.get('type')!r} para a página {pagina}")
        time.sleep(self.pausa)
        return dados

    def listar_materias(self, dia: date) -> Iterator[dict[str, Any]]:
        ts = timestamp_do_dia(dia)
        primeira = self._pagina_do_diario(ts, 1, "", "")

        # Sem edição no dia, o site devolve a última publicada: nesse caso não há nada a coletar.
        data_retornada = (primeira.get("data") or [None])[0]
        if data_retornada != dia.strftime("%Y%m%d"):
            log.info("DODF sem edição em %s (site devolveu %s)", dia, data_retornada)
            return

        tipos = primeira.get("lstTiposJornais") or [{"tipo_jornal": "", "letra": None}]
        vistos: set[str] = set()
        for tipo in tipos:
            tp_jornal = str(tipo.get("tipo_jornal") or "")
            letra = tipo.get("letra") or ""
            pagina, total_paginas = 1, 1
            while pagina <= total_paginas:
                dados = self._pagina_do_diario(ts, pagina, tp_jornal, letra)
                total_paginas = int(dados.get("totalPaginas") or 1)
                for materia in dados.get("lstMaterias") or []:
                    co = str(materia.get("coMateria"))
                    if co not in vistos:
                        vistos.add(co)
                        yield materia
                pagina += 1

    def texto_completo(self, materia: dict[str, Any]) -> str | None:
        resposta = self.client.get(url_materia(materia).removeprefix(BASE_URL))
        resposta.raise_for_status()
        time.sleep(self.pausa)
        return extrair_texto_materia(resposta.text)

    def coletar(self, dia: date, ja_conhecido: JaConhecido) -> Iterator[PublicacaoColetada]:
        for materia in self.listar_materias(dia):
            id_externo = str(materia["coMateria"])
            titulo = html.unescape(materia.get("titulo") or "").strip() or None
            trecho = html.unescape(materia.get("texto") or "")
            if ja_conhecido(id_externo) or not talvez_concurso(titulo or "", trecho):
                continue
            texto = self.texto_completo(materia)
            if not texto:
                log.warning("DODF: matéria %s sem texto (pode ser só imagem)", id_externo)
                continue
            yield PublicacaoColetada(
                fonte=self.fonte,
                id_externo=id_externo,
                data_publicacao=dia,
                texto=texto,
                titulo=titulo,
                secao=materia.get("secao"),
                orgao=orgao_da_materia(materia),
                tipo_ato=materia.get("tipo"),
                url=url_materia(materia),
            )
