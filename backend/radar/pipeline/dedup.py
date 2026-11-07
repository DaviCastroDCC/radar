"""Regras para reconhecer o MESMO concurso vindo de fontes diferentes.

O edital de um concurso federal da Cebraspe sai no site da banca e no DOU; o de um
concurso estadual, no site da banca e no diário do estado. O usuário deve receber um
alerta só. Funções puras: o acesso ao banco fica em radar.pipeline.processor.
"""

import re

from radar.texto import normalizar

# Palavras que aparecem em quase todo nome de órgão e não ajudam a distinguir.
_GENERICAS = {
    "de", "do", "da", "dos", "das", "e", "o", "a", "em", "para",
    "estado", "estadual", "secretaria", "governo", "federal", "nacional", "municipal",
    "municipio", "prefeitura", "ministerio", "instituto", "fundacao", "publico", "publica",
}  # fmt: skip

SIGLAS_UF = {
    "ac": "acre", "al": "alagoas", "ap": "amapa", "am": "amazonas", "ba": "bahia", "ce": "ceara",
    "df": "distrito federal", "es": "espirito santo", "go": "goias", "ma": "maranhao",
    "mt": "mato grosso", "ms": "mato grosso do sul", "mg": "minas gerais", "pa": "para",
    "pb": "paraiba", "pr": "parana", "pe": "pernambuco", "pi": "piaui", "rj": "rio de janeiro",
    "rn": "rio grande do norte", "rs": "rio grande do sul", "ro": "rondonia", "rr": "roraima",
    "sc": "santa catarina", "sp": "sao paulo", "se": "sergipe", "to": "tocantins",
}  # fmt: skip


def numero_e_ano(texto: str | None) -> tuple[int, int | None] | None:
    """'Edital nº 01/2026 - SEEDF' -> (1, 2026); 'Edital nº 7' -> (7, None)."""
    if not texto:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d{4})", texto)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"n[ºo°.]*\s*(\d+)", normalizar(texto))
    if m:
        ano = re.search(r"\b(20\d{2})\b", texto)
        return int(m.group(1)), int(ano.group(1)) if ano else None
    return None


def numeros_compativeis(a: str | None, b: str | None) -> bool:
    """Mesmo número; o ano só conta se os dois lados tiverem."""
    na, nb = numero_e_ano(a), numero_e_ano(b)
    if na is None or nb is None or na[0] != nb[0]:
        return False
    return na[1] is None or nb[1] is None or na[1] == nb[1]


# Siglas que também são palavras comuns em nomes de órgãos: só valem por extenso.
_SIGLAS_AMBIGUAS = {"SE", "TO", "PA", "AL", "MA", "ES"}


def ufs_do_orgao(orgao: str | None) -> set[str]:
    """UFs citadas no nome do órgão, por extenso ou por sigla em maiúsculas ('DF', 'PE')."""
    if not orgao:
        return set()
    texto = normalizar(orgao)
    ufs = set()
    for sigla, nome in sorted(SIGLAS_UF.items(), key=lambda kv: -len(kv[1])):  # "mato grosso do sul" antes
        # "Pará" normalizado vira "para", que é preposição: exige o acento no original.
        alvo = orgao.lower() if sigla == "pa" else texto
        nome_alvo = "pará" if sigla == "pa" else nome
        if re.search(rf"\b{nome_alvo}\b", alvo):
            ufs.add(sigla)
            texto = re.sub(rf"\b{nome}\b", " ", texto)
    for sigla in re.findall(r"\b[A-Z]{2}\b", orgao):
        if sigla.lower() in SIGLAS_UF and sigla not in _SIGLAS_AMBIGUAS:
            ufs.add(sigla.lower())
    return ufs


def tokens_do_orgao(orgao: str | None) -> set[str]:
    """Palavras que distinguem o órgão, sem as genéricas e sem os nomes de UF (tratados à parte)."""
    texto = normalizar(orgao or "")
    for nome in sorted(SIGLAS_UF.values(), key=len, reverse=True):
        texto = re.sub(rf"\b{nome}\b", " ", texto)
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    return {p for p in texto.split() if p not in _GENERICAS and p not in SIGLAS_UF and not p.isdigit()}


def orgaos_parecidos(a: str | None, b: str | None, limiar: float = 0.6) -> bool:
    ua, ub = ufs_do_orgao(a), ufs_do_orgao(b)
    if ua and ub and not ua & ub:
        return False  # estados diferentes: nunca é o mesmo órgão
    ta, tb = tokens_do_orgao(a), tokens_do_orgao(b)
    if not ta or not tb:
        return False
    # NA DÚVIDA, NÃO JUNTAR: juntar errado faz o usuário perder um concurso; não juntar só
    # gera um alerta duplicado. Sem UF em comum para ancorar, uma palavra só é pouco
    # ("Educação" casaria com a Educação de qualquer estado).
    if not ua & ub and min(len(ta), len(tb)) < 2:
        return False
    if ta <= tb or tb <= ta:  # "Educação DF" ⊂ "SEE Educação DF"
        return True
    return len(ta & tb) / len(ta | tb) >= limiar


def mesmo_concurso(
    orgao_a: str | None, numero_a: str | None, orgao_b: str | None, numero_b: str | None
) -> bool:
    return numeros_compativeis(numero_a, numero_b) and orgaos_parecidos(orgao_a, orgao_b)
