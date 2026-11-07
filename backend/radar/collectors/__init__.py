from radar.collectors.base import Coletor, ErroColeta, PublicacaoColetada
from radar.config import Settings


def criar_coletores(settings: Settings) -> list[Coletor]:
    from radar.collectors.dodf import ColetorDODF
    from radar.collectors.dou_inlabs import ColetorDOU

    disponiveis: dict[str, Coletor] = {}
    for fonte in settings.lista_fontes:
        if fonte == "dodf":
            disponiveis[fonte] = ColetorDODF(settings)
        elif fonte == "dou":
            disponiveis[fonte] = ColetorDOU(settings)
        else:
            raise ValueError(f"Fonte desconhecida: {fonte}")
    return list(disponiveis.values())


__all__ = ["Coletor", "ErroColeta", "PublicacaoColetada", "criar_coletores"]
