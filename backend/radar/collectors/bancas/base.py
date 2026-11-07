"""Base dos coletores de bancas organizadoras.

Cada banca só implementa `listar_documentos()`: quais documentos existem, com data e URL.
Esta classe cuida do resto: janela de datas, filtro por tipo de documento, download e
extração de texto. Adicionar uma banca nova custa algumas dezenas de linhas.

Regra de ouro: respeitar o robots.txt e nunca contornar bloqueio (403, captcha, WAF).
Banca que bloqueia robôs entra pela camada de diários oficiais, onde o órgão contratante
é obrigado a publicar.
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from radar.collectors.base import JaConhecido, PublicacaoColetada
from radar.config import Settings
from radar.documentos import ErroDocumento, texto_de_documento

log = logging.getLogger(__name__)

# Documentos que mudam a vida do candidato e cabem num alerta.
RELEVANTE = re.compile(r"abertura|retifica|prorroga|reabertura|suspens|cancela|anula|adiamento|adiad", re.I)
# Fora: versões acessíveis duplicadas e listas de resultado (enormes e cheias de dados pessoais).
IGNORAR = re.compile(
    r"vlibras|libras|resultado|gabarito|convoca|locais? de prova|homologa|classifica|relação|relacao", re.I
)


@dataclass(frozen=True)
class DocumentoBanca:
    id_externo: str
    url: str
    descricao: str
    concurso: str
    orgao: str | None
    data: date


def documento_relevante(descricao: str) -> bool:
    return bool(RELEVANTE.search(descricao)) and not IGNORAR.search(descricao)


class ColetorBanca(ABC):
    fonte: str
    # Bancas mudam devagar: não precisam ser consultadas a cada ciclo do worker.
    intervalo_min: int = 30
    # Na primeira coleta, só documentos recentes (não alertar sobre edital de meses atrás).
    janela_dias: int = 15

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.pausa = settings.pausa_entre_requisicoes_s
        self.client = client or httpx.Client(
            headers={"User-Agent": settings.http_user_agent},
            timeout=httpx.Timeout(60.0),
            follow_redirects=True,
        )

    @abstractmethod
    def listar_documentos(self) -> Iterable[DocumentoBanca]: ...

    def _get(self, url: str, **kwargs) -> httpx.Response:
        resposta = self.client.get(url, **kwargs)
        time.sleep(self.pausa)
        resposta.raise_for_status()
        return resposta

    def baixar_texto(self, doc: DocumentoBanca) -> str | None:
        resposta = self._get(doc.url)
        try:
            return texto_de_documento(resposta.content, resposta.headers.get("content-type", ""), doc.url)
        except ErroDocumento as e:
            log.warning("documento ignorado: %s", e, extra={"fonte": self.fonte, "url": doc.url})
            return None

    def coletar(self, dia: date, ja_conhecido: JaConhecido) -> Iterator[PublicacaoColetada]:
        limite = dia - timedelta(days=self.janela_dias)
        for doc in self.listar_documentos():
            if doc.data < limite or ja_conhecido(doc.id_externo) or not documento_relevante(doc.descricao):
                continue
            texto = self.baixar_texto(doc)
            if not texto:
                continue
            yield PublicacaoColetada(
                fonte=self.fonte,
                id_externo=doc.id_externo,
                data_publicacao=doc.data,
                texto=texto,
                titulo=f"{doc.descricao} – {doc.concurso}",
                orgao=doc.orgao,
                tipo_ato="Edital",
                url=doc.url,
            )
