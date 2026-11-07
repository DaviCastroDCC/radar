from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ErroColeta(Exception):
    """Falha que impede a coleta de uma fonte (login recusado, site fora do ar...)."""


@dataclass(frozen=True)
class PublicacaoColetada:
    fonte: str
    id_externo: str
    data_publicacao: date
    texto: str
    titulo: str | None = None
    secao: str | None = None
    orgao: str | None = None
    tipo_ato: str | None = None
    url: str | None = None


# Recebe o id externo e diz se ele já está no banco (para não baixar de novo).
JaConhecido = Callable[[str], bool]


class Coletor(Protocol):
    fonte: str

    def coletar(self, dia: date, ja_conhecido: JaConhecido) -> Iterator[PublicacaoColetada]:
        """Devolve as publicações do dia que podem ser de concurso (pré-filtro barato)."""
        ...
