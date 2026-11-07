"""Utilitários de texto: HTML -> texto limpo e normalização para comparação."""

import re
import unicodedata

from bs4 import BeautifulSoup

_ESPACOS = re.compile(r"[ \t ]+")
_LINHAS_VAZIAS = re.compile(r"\n\s*\n+")


def html_para_texto(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    texto = soup.get_text("\n")
    texto = _ESPACOS.sub(" ", texto)
    texto = "\n".join(linha.strip() for linha in texto.splitlines())
    return _LINHAS_VAZIAS.sub("\n\n", texto).strip()


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples: 'Concurso  Público' -> 'concurso publico'."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()
