"""Interpretação dos comandos do bot (puro, sem Telegram nem banco)."""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html import escape

from radar.texto import normalizar

# fmt: off
UFS = frozenset([
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
])
# fmt: on

ESCOLARIDADES = {
    "fundamental": "fundamental",
    "medio": "medio",
    "tecnico": "tecnico",
    "superior": "superior",
    "graduacao": "superior",
}


@dataclass
class NovoFiltro:
    palavras: str = ""
    ufs: list[str] = field(default_factory=list)
    escolaridades: list[str] = field(default_factory=list)
    salario_min: Decimal | None = None

    def descricao(self) -> str:
        """Texto em HTML do Telegram (as palavras do usuário são escapadas)."""
        partes = [f"cargo/órgão: <b>{escape(self.palavras)}</b>" if self.palavras else "qualquer cargo"]
        partes.append("UF: " + (", ".join(self.ufs) if self.ufs else "todas"))
        if self.escolaridades:
            partes.append("escolaridade: " + ", ".join(self.escolaridades))
        if self.salario_min is not None:
            partes.append(f"salário a partir de R$ {self.salario_min:,.0f}".replace(",", "."))
        return " · ".join(partes)


AJUDA_FILTRO = (
    "Use assim:\n"
    "<code>/filtro analista ti; uf=DF,GO; salario=6000; escolaridade=superior</code>\n\n"
    "Só a primeira parte (cargo ou órgão) é livre. As outras são opcionais:\n"
    "• <b>uf</b>: siglas separadas por vírgula\n"
    "• <b>salario</b>: valor mínimo em reais\n"
    "• <b>escolaridade</b>: fundamental, medio, tecnico ou superior"
)


def _parse_valor(texto: str) -> Decimal:
    limpo = re.sub(r"[^\d,\.]", "", texto)
    # "6.500,00" -> "6500.00"; "6500" -> "6500"
    limpo = limpo.replace(".", "").replace(",", ".") if "," in limpo else limpo.replace(".", "")
    try:
        return Decimal(limpo)
    except InvalidOperation as e:
        raise ValueError(f"Salário inválido: {texto}") from e


def parse_filtro(texto: str) -> NovoFiltro:
    """'analista ti; uf=DF,GO; salario=6000; escolaridade=superior' -> NovoFiltro"""
    filtro = NovoFiltro()
    for parte in (p.strip() for p in texto.split(";")):
        if not parte:
            continue
        chave, sep, valor = parte.partition("=")
        chave_norm = normalizar(chave)
        if not sep:
            filtro.palavras = " ".join(parte.split())[:200]
        elif chave_norm == "uf":
            ufs = [u.strip().upper() for u in valor.split(",") if u.strip()]
            invalidas = [u for u in ufs if u not in UFS and u != "BR"]
            if invalidas:
                raise ValueError(f"UF inválida: {', '.join(invalidas)}")
            filtro.ufs = [u for u in ufs if u != "BR"]
        elif chave_norm in ("salario", "salario_min"):
            filtro.salario_min = _parse_valor(valor)
        elif chave_norm == "escolaridade":
            escs = []
            for e in valor.split(","):
                e_norm = normalizar(e)
                if not e_norm:
                    continue
                if e_norm not in ESCOLARIDADES:
                    raise ValueError(f"Escolaridade inválida: {e.strip()}")
                escs.append(ESCOLARIDADES[e_norm])
            filtro.escolaridades = sorted(set(escs))
        else:
            raise ValueError(f"Não entendi '{chave.strip()}'.")
    if not (filtro.palavras or filtro.ufs or filtro.escolaridades or filtro.salario_min):
        raise ValueError("Filtro vazio.")
    return filtro
