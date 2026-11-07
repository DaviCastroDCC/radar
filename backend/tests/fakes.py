"""Dublês de teste e construtores de dados, sem chamadas externas."""

from datetime import date
from types import SimpleNamespace

from radar import db
from radar.collectors.base import PublicacaoColetada
from radar.models import Filtro, Usuario
from radar.pipeline.extractor import EditalExtraido
from radar.pipeline.processor import salvar_publicacao
from radar.relogio import agora
from radar.usuarios import TERMOS_VERSAO

CARGO_PROFESSOR = {
    "nome": "Professor",
    "escolaridade": "superior",
    "vagas": 100,
    "cadastro_reserva": True,
    "salario": 5800.5,
}


def extraido_exemplo(**mudancas) -> EditalExtraido:
    base = {
        "e_concurso": True,
        "tipo": "abertura",
        "orgao": "SEEDF",
        "banca": "Cebraspe",
        "titulo": "Concurso SEEDF 2026",
        "numero_edital": "Edital nº 1/2026",
        "edital_referenciado": None,
        "uf": "DF",
        "cidades": ["Brasília"],
        "cargos": [CARGO_PROFESSOR],
        "inscricao_inicio": "2026-11-10",
        "inscricao_fim": "2026-11-30",
        "data_prova": "2027-02-15",
        "taxa_inscricao": 120.0,
        "link_inscricao": "https://www.cebraspe.org.br",
        "resumo": "Concurso com 100 vagas.",
    }
    return EditalExtraido.model_validate({**base, **mudancas})


class ClienteAnthropicFalso:
    """Imita client.messages.parse() do SDK da Anthropic e guarda os argumentos recebidos."""

    def __init__(self, stop_reason: str = "end_turn", parsed: EditalExtraido | None = None) -> None:
        self.chamadas: list[dict] = []
        self._resposta = SimpleNamespace(
            stop_reason=stop_reason,
            parsed_output=parsed,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        return self._resposta


class ExtratorFalso:
    """Devolve extrações pré-definidas pelo título da publicação."""

    modelo = "fake"

    def __init__(self, respostas: dict[str, EditalExtraido]) -> None:
        self.respostas = respostas

    def extrair(self, *, titulo, **_):
        return self.respostas[titulo]


def publicar(id_externo: str, titulo: str, texto: str, fonte: str = "dodf") -> None:
    salvar_publicacao(
        PublicacaoColetada(
            fonte=fonte,
            id_externo=id_externo,
            data_publicacao=date.today(),
            texto=texto,
            titulo=titulo,
            orgao="Secretaria de Estado de Educação",
            url=f"https://dodf/{id_externo}",
        )
    )


def criar_usuario(chat_id: int, *, aceitou_termos: bool = True, **filtro) -> int:
    """Usuário com um filtro; por padrão já com consentimento na versão vigente."""
    with db.session_scope() as s:
        usuario = Usuario(
            telegram_chat_id=chat_id,
            termos_aceitos_em=agora() if aceitou_termos else None,
            termos_versao=TERMOS_VERSAO if aceitou_termos else None,
        )
        s.add(usuario)
        s.flush()
        s.add(Filtro(usuario_id=usuario.id, **filtro))
        return usuario.id


def pdf_com_texto(*paginas: str) -> bytes:
    """PDF mínimo e válido, uma página por argumento (texto ASCII simples, fonte Helvetica)."""
    objetos: list[bytes] = []
    n_paginas = len(paginas)
    # 1: catálogo, 2: árvore de páginas, 3: fonte; depois, por página: página + conteúdo
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_paginas))
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_paginas} >>".encode())
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, texto in enumerate(paginas):
        linhas = texto.replace("(", "[").replace(")", "]").splitlines() or [""]
        comandos = "BT /F1 10 Tf 40 800 Td 12 TL " + " ".join(f"({linha}) '" for linha in linhas) + " ET"
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {5 + 2 * i} 0 R >>".encode()
        )
        objetos.append(f"<< /Length {len(comandos)} >>\nstream\n{comandos}\nendstream".encode())

    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for numero, corpo in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{numero} 0 obj\n".encode() + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    saida += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(saida)
