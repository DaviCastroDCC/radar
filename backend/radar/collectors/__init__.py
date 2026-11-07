from collections.abc import Callable

from radar.collectors.base import Coletor, ErroColeta, PublicacaoColetada
from radar.config import Settings

# Diários oficiais publicam todo dia útil: nada lido num dia útil é sinal de problema.
# Bancas publicam quando há novidade: zero documentos é normal (ver radar.saude).
FONTES_DIARIOS = {"dodf", "dou"}


def _registro() -> dict[str, Callable[[Settings], Coletor]]:
    from radar.collectors.bancas.cebraspe import ColetorCebraspe
    from radar.collectors.dodf import ColetorDODF
    from radar.collectors.dou_inlabs import ColetorDOU

    return {
        "dodf": ColetorDODF,
        "dou": ColetorDOU,
        "cebraspe": ColetorCebraspe,
    }


def fontes_disponiveis() -> list[str]:
    return sorted(_registro())


def criar_coletores(settings: Settings) -> list[Coletor]:
    registro = _registro()
    desconhecidas = [f for f in settings.lista_fontes if f not in registro]
    if desconhecidas:
        raise ValueError(
            f"Fonte(s) desconhecida(s): {', '.join(desconhecidas)}. Disponíveis: {fontes_disponiveis()}"
        )
    return [registro[fonte](settings) for fonte in dict.fromkeys(settings.lista_fontes)]


__all__ = [
    "FONTES_DIARIOS",
    "Coletor",
    "ErroColeta",
    "PublicacaoColetada",
    "criar_coletores",
    "fontes_disponiveis",
]
