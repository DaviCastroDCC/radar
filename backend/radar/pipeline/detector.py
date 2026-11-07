"""Filtro barato (sem IA) que decide se uma publicação merece ir para a extração.

Duas etapas:
- talvez_concurso(): pré-filtro bem largo, usado na coleta com título + trecho.
- detectar(): pontuação no texto completo; só o que passar vai para o LLM.

Errar para o lado de deixar passar é aceitável: a IA descarta o que não for concurso.
Deixar de fora um edital de verdade não é.
"""

import re
from dataclasses import dataclass

from radar.texto import normalizar

GATILHOS = ("concurso publico", "concursos publicos", "processo seletivo", "selecao publica")

POSITIVOS: dict[str, int] = {
    "concurso publico": 5,
    "processo seletivo": 3,
    "edital de abertura": 5,
    "edital normativo": 4,
    "abertura de inscricoes": 4,
    "abertura das inscricoes": 4,
    "torna publica a abertura": 4,
    "torna publica a realizacao": 3,
    "provimento de cargos": 3,
    "provimento de vagas": 3,
    "cadastro de reserva": 2,
    "cadastro reserva": 2,
    "taxa de inscricao": 3,
    "isencao da taxa": 2,
    "prova objetiva": 2,
    "provas objetivas": 2,
    "conteudo programatico": 2,
    "remuneracao": 1,
    "vencimento basico": 1,
    "vagas": 1,
    "retificacao": 1,
    "retifica": 1,
    "prorrogacao das inscricoes": 3,
    "cebraspe": 3,
    "fundacao getulio vargas": 3,
    "fundacao carlos chagas": 3,
    "instituto aocp": 3,
    "cesgranrio": 3,
    "vunesp": 3,
    "quadrix": 3,
    "idecan": 3,
    "ibfc": 3,
}

NEGATIVOS: dict[str, int] = {
    "pregao eletronico": -6,
    "licitacao": -4,
    "tomada de precos": -6,
    "dispensa de licitacao": -6,
    "extrato de contrato": -6,
    "ata de registro de precos": -6,
    "leilao": -4,
    "credenciamento": -2,
    "chamamento publico": -2,
    "nomear os candidatos": -4,
    "nomeacao dos candidatos": -4,
    "torna sem efeito a nomeacao": -5,
    "aposentadoria": -3,
}

LIMIAR = 6

_RETIFICACAO = re.compile(r"\bretifica(cao|-se|r)?\b|\bprorroga")


@dataclass(frozen=True)
class Deteccao:
    candidato: bool
    score: int
    parece_retificacao: bool


def talvez_concurso(titulo: str, trecho: str) -> bool:
    texto = normalizar(f"{titulo} {trecho}")
    if any(g in texto for g in GATILHOS):
        return True
    # No DODF o trecho é curto; editais de concurso costumam ter "EDITAL" no título.
    return normalizar(titulo).startswith("edital")


def detectar(titulo: str, texto: str) -> Deteccao:
    norm = normalizar(f"{titulo}\n{texto}")
    if not any(g in norm for g in GATILHOS):
        return Deteccao(candidato=False, score=0, parece_retificacao=False)

    score = 0
    for termo, peso in {**POSITIVOS, **NEGATIVOS}.items():
        if termo in norm:
            score += peso

    titulo_norm = normalizar(titulo)
    parece_retificacao = bool(_RETIFICACAO.search(titulo_norm)) or bool(_RETIFICACAO.search(norm[:600]))
    # Retificações são curtas e pontuam pouco, mas importam para quem acompanha o edital.
    limiar = 3 if parece_retificacao else LIMIAR
    return Deteccao(candidato=score >= limiar, score=score, parece_retificacao=parece_retificacao)
