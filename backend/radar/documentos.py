"""Extração de texto de documentos baixados (PDF e HTML).

PDF via pypdfium2 (licença Apache/BSD). O PyMuPDF foi descartado por ser AGPL,
o que traria obrigações de licença para um serviço comercial.
"""

import re

import pypdfium2 as pdfium

from radar.texto import html_para_texto

MAX_PAGINAS = 400  # editais grandes têm ~150; acima disso quase sempre é anexo de resultado
MIN_CARACTERES_POR_PAGINA = 80  # abaixo disso o PDF provavelmente é imagem escaneada


class ErroDocumento(Exception):
    pass


class PdfEscaneado(ErroDocumento):
    """PDF sem camada de texto: precisaria de OCR."""


def texto_de_pdf(conteudo: bytes) -> str:
    try:
        pdf = pdfium.PdfDocument(conteudo)
    except pdfium.PdfiumError as e:
        raise ErroDocumento(f"PDF inválido: {e}") from e
    try:
        paginas = min(len(pdf), MAX_PAGINAS)
        partes = []
        for i in range(paginas):
            pagina = pdf[i]
            texto_pagina = pagina.get_textpage()
            partes.append(texto_pagina.get_text_range())
            texto_pagina.close()
            pagina.close()
    finally:
        pdf.close()

    texto = "\n".join(partes).replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t ]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n\n", texto).strip()
    if paginas and len(texto) < MIN_CARACTERES_POR_PAGINA * paginas:
        raise PdfEscaneado(f"{paginas} páginas com só {len(texto)} caracteres de texto")
    return texto


def texto_de_documento(conteudo: bytes, content_type: str = "", url: str = "") -> str:
    tipo = content_type.lower()
    if "pdf" in tipo or conteudo.startswith(b"%PDF") or url.lower().endswith(".pdf"):
        return texto_de_pdf(conteudo)
    if "html" in tipo or url.lower().endswith((".html", ".htm")):
        return html_para_texto(conteudo.decode("utf-8", errors="replace"))
    raise ErroDocumento(f"tipo de documento não suportado: {content_type or url}")
