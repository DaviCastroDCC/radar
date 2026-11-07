"""Decide se um edital interessa a um filtro de usuário. Funções puras e fáceis de testar.

Regras:
- palavras: todos os termos precisam aparecer (no cargo, no órgão ou no título).
  Siglas comuns são expandidas ("ti" também casa com "tecnologia da informação").
- ufs: vazio = qualquer UF. Edital nacional ("BR") ou sem UF casa com todos.
- escolaridades: vazio = qualquer. Cargo sem escolaridade informada passa.
- salario_min: cargo sem salário informado passa (melhor avisar do que perder).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from radar.texto import normalizar

STOPWORDS = {"de", "da", "do", "das", "dos", "e", "para", "em", "a", "o", "na", "no"}

SINONIMOS: dict[str, list[str]] = {
    "ti": ["tecnologia da informacao", "informatica"],
    "adm": ["administrativo", "administracao"],
    "pf": ["policia federal"],
    "prf": ["policia rodoviaria federal"],
    "pm": ["policia militar"],
    "pc": ["policia civil"],
    "pcdf": ["policia civil do distrito federal"],
    "pmdf": ["policia militar do distrito federal"],
    "cbm": ["corpo de bombeiros"],
    "tj": ["tribunal de justica"],
    "trt": ["tribunal regional do trabalho"],
    "trf": ["tribunal regional federal"],
    "tre": ["tribunal regional eleitoral"],
    "inss": ["instituto nacional do seguro social"],
    "seedf": ["secretaria de estado de educacao do distrito federal"],
    "ses": ["secretaria de saude", "secretaria de estado de saude"],
}


@dataclass(frozen=True)
class CargoInfo:
    nome: str
    escolaridade: str = "nao_informado"
    salario: Decimal | float | None = None


@dataclass(frozen=True)
class EditalInfo:
    titulo: str | None
    orgao: str | None
    uf: str | None
    resumo: str | None = None
    cargos: Sequence[CargoInfo] = field(default_factory=tuple)


@dataclass(frozen=True)
class FiltroInfo:
    palavras: str = ""
    ufs: Sequence[str] = field(default_factory=tuple)
    escolaridades: Sequence[str] = field(default_factory=tuple)
    salario_min: Decimal | float | None = None


@dataclass(frozen=True)
class Casamento:
    cargos: list[str]


def termos_do_filtro(palavras: str) -> list[list[str]]:
    """'Analista TI' -> [['analista'], ['ti', 'tecnologia da informacao', 'informatica']]"""
    termos = []
    for token in re.split(r"[\s,;/]+", normalizar(palavras)):
        if not token or token in STOPWORDS:
            continue
        termos.append([token, *_singulares(token), *SINONIMOS.get(token, [])])
    return termos


def _singulares(token: str) -> list[str]:
    """Plural simples: 'professores' -> 'professor', 'analistas' -> 'analista'."""
    if len(token) <= 4 or not token.endswith("s"):
        return []
    if token.endswith(("res", "zes", "ses")):
        return [token[:-2]]
    return [token[:-1]]


def _contem(texto_norm: str, termo: str) -> bool:
    # Termos curtos (siglas) exigem palavra inteira; os demais aceitam sufixo (plural, gênero).
    padrao = rf"\b{re.escape(termo)}\b" if len(termo) <= 3 else rf"\b{re.escape(termo)}"
    return re.search(padrao, texto_norm) is not None


def _casa_palavras(texto: str, termos: list[list[str]]) -> bool:
    norm = normalizar(texto)
    return all(any(_contem(norm, alt) for alt in alternativas) for alternativas in termos)


def _casa_uf(edital: EditalInfo, filtro: FiltroInfo) -> bool:
    if not filtro.ufs:
        return True
    uf = (edital.uf or "").upper()
    if uf in ("", "BR"):
        return True
    return uf in {u.upper() for u in filtro.ufs}


def casar(edital: EditalInfo, filtro: FiltroInfo) -> Casamento | None:
    if not _casa_uf(edital, filtro):
        return None

    termos = termos_do_filtro(filtro.palavras)
    contexto = f"{edital.orgao or ''} {edital.titulo or ''}"

    if not edital.cargos:
        if termos and not _casa_palavras(f"{contexto} {edital.resumo or ''}", termos):
            return None
        return Casamento(cargos=[])

    escolaridades = set(filtro.escolaridades)
    salario_min = Decimal(str(filtro.salario_min)) if filtro.salario_min is not None else None
    cargos_ok = []
    for cargo in edital.cargos:
        if escolaridades and cargo.escolaridade not in escolaridades | {"nao_informado"}:
            continue
        abaixo_do_minimo = (
            salario_min is not None
            and cargo.salario is not None
            and Decimal(str(cargo.salario)) < salario_min
        )
        if abaixo_do_minimo:
            continue
        if termos and not _casa_palavras(f"{cargo.nome} {contexto}", termos):
            continue
        cargos_ok.append(cargo.nome)

    return Casamento(cargos=cargos_ok) if cargos_ok else None
