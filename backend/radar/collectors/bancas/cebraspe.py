"""Cebraspe (https://www.cebraspe.org.br/concursos).

O site é uma aplicação React que consome uma API JSON pública:
- GET /cebraspe/eventos/tipo/concursos/  -> concursos agrupados por fase
- GET /cebraspe/eventos/{identificador}  -> detalhe, com a lista de documentos do edital
Os arquivos ficam no CDN (cdn.cebraspe.org.br). robots.txt do site e do CDN: sem restrições.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from radar.collectors.bancas.base import ColetorBanca, DocumentoBanca

API = "https://apis.cebraspe.org.br/cebraspe"
CDN = "https://cdn.cebraspe.org.br"
FASES_ATIVAS = {"Novos", "Inscrições Abertas", "Em Andamento"}


def url_arquivo(evento: dict[str, Any], arquivo: dict[str, Any]) -> str:
    if arquivo.get("isGuid"):
        return f"{CDN}/{arquivo['nomeArquivo']}"
    return f"{CDN}/{evento['eventoTipo']}/{evento['eventoURL']}/arquivos/{arquivo['nomeArquivo']}"


def _data(arquivo: dict[str, Any]) -> datetime | None:
    bruto = arquivo.get("dataArquivoObj") or ""
    try:
        return datetime.fromisoformat(bruto)
    except ValueError:
        try:
            return datetime.strptime(arquivo.get("dataArquivo") or "", "%d/%m/%Y %H:%M")
        except ValueError:
            return None


def documentos_do_evento(evento: dict[str, Any]) -> Iterator[DocumentoBanca]:
    for arquivo in evento.get("arquivosEdital") or []:
        quando = _data(arquivo)
        if quando is None or not arquivo.get("nomeArquivo"):
            continue
        yield DocumentoBanca(
            id_externo=f"{evento['eventoURL']}/{arquivo['nomeArquivo']}",
            url=url_arquivo(evento, arquivo),
            descricao=(arquivo.get("descricaoArquivo") or "").strip(),
            concurso=evento.get("eventoNomeCompleto")
            or evento.get("eventoNomeAbreviado")
            or evento["eventoURL"],
            orgao=evento.get("eventoNomeCompleto") or evento.get("eventoNomeAbreviado"),
            data=quando.date(),
        )


class ColetorCebraspe(ColetorBanca):
    fonte = "cebraspe"

    def listar_documentos(self) -> Iterator[DocumentoBanca]:
        grupos = self._get(f"{API}/eventos/tipo/concursos/").json()
        for grupo in grupos:
            if grupo.get("faseEvento") not in FASES_ATIVAS:
                continue
            for resumo in grupo.get("eventos") or []:
                if not resumo.get("eventoURL"):
                    continue
                evento = self._get(f"{API}/eventos/{resumo['eventoURL']}").json()
                yield from documentos_do_evento(evento)
