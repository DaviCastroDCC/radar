"""Dublês de teste e construtores de dados, sem chamadas externas."""

from datetime import date
from types import SimpleNamespace

from radar import db
from radar.collectors.base import PublicacaoColetada
from radar.models import Filtro, Usuario
from radar.pipeline.extractor import EditalExtraido
from radar.pipeline.processor import salvar_publicacao

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


def publicar(id_externo: str, titulo: str, texto: str) -> None:
    salvar_publicacao(
        PublicacaoColetada(
            fonte="dodf",
            id_externo=id_externo,
            data_publicacao=date.today(),
            texto=texto,
            titulo=titulo,
            orgao="Secretaria de Estado de Educação",
            url=f"https://dodf/{id_externo}",
        )
    )


def criar_usuario(chat_id: int, **filtro) -> int:
    with db.session_scope() as s:
        usuario = Usuario(telegram_chat_id=chat_id, nome=f"user{chat_id}")
        s.add(usuario)
        s.flush()
        s.add(Filtro(usuario_id=usuario.id, **filtro))
        return usuario.id
