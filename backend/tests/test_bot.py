"""Handlers do bot com dublês do Telegram (sem rede) e banco real."""

import asyncio
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select

from radar import db, usuarios
from radar.bot import main as bot
from radar.bot import textos
from radar.models import Usuario
from tests.fakes import criar_usuario

CHAT = 777


@dataclass
class MensagemFalsa:
    respostas: list[dict[str, Any]] = field(default_factory=list)

    async def reply_text(self, texto, **kwargs):
        self.respostas.append({"texto": texto, **kwargs})

    async def reply_document(self, **kwargs):
        self.respostas.append(kwargs)

    @property
    def ultima(self) -> dict[str, Any]:
        return self.respostas[-1]


@dataclass
class CallbackFalso:
    data: str
    respostas: list[tuple[str | None, bool]] = field(default_factory=list)
    editado: str | None = None

    async def answer(self, texto=None, show_alert=False):
        self.respostas.append((texto, show_alert))

    async def edit_message_text(self, texto, **_):
        self.editado = texto


def _rodar(handler, *args: str, callback: str | None = None):
    mensagem = MensagemFalsa()
    query = CallbackFalso(callback) if callback else None
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=CHAT), effective_message=mensagem, callback_query=query
    )
    asyncio.run(handler(update, SimpleNamespace(args=list(args))))
    return mensagem, query


def _botoes(resposta: dict[str, Any]) -> list[str]:
    teclado = resposta["reply_markup"].inline_keyboard
    return [b.callback_data or b.url for linha in teclado for b in linha]


def _usuarios() -> int:
    with db.session_scope() as s:
        return s.scalar(select(func.count()).select_from(Usuario))


# ------------------------------ consentimento ------------------------------
def test_start_pede_aceite_e_botao_aceita(limpo):
    mensagem, _ = _rodar(bot.start)
    assert mensagem.ultima["texto"] == textos.TERMOS_RESUMO
    assert bot.ACEITAR_TERMOS in _botoes(mensagem.ultima)

    _, query = _rodar(bot.botao, callback=bot.ACEITAR_TERMOS)
    assert query.editado == textos.BOAS_VINDAS
    assert usuarios.registrar(CHAT) is True


def test_start_de_quem_ja_aceitou_mostra_boas_vindas(limpo):
    criar_usuario(CHAT)
    mensagem, _ = _rodar(bot.start)
    assert mensagem.ultima["texto"] == textos.BOAS_VINDAS


def test_filtro_sem_aceite_pede_termos(limpo):
    _rodar(bot.start)
    mensagem, _ = _rodar(bot.filtro, "professor")
    assert mensagem.ultima["texto"] == textos.TERMOS_RESUMO


# ------------------------------ filtros ------------------------------
def test_criar_listar_e_remover_filtro(limpo):
    criar_usuario(CHAT, palavras="enfermeiro")
    mensagem, _ = _rodar(bot.filtro, "analista", "ti;", "uf=DF")
    assert mensagem.ultima["texto"].startswith("✅ Filtro #2 criado")

    mensagem, _ = _rodar(bot.filtros)
    assert "#1" in mensagem.ultima["texto"]
    assert "analista ti" in mensagem.ultima["texto"]

    mensagem, _ = _rodar(bot.remover, "#2")
    assert mensagem.ultima["texto"] == "🗑 Filtro #2 removido."
    mensagem, _ = _rodar(bot.remover, "2")
    assert "Não achei" in mensagem.ultima["texto"]


def test_filtro_invalido_e_sem_argumento(limpo):
    criar_usuario(CHAT)
    mensagem, _ = _rodar(bot.filtro, "uf=XX")
    assert mensagem.ultima["texto"].startswith("⚠️ UF inválida")
    mensagem, _ = _rodar(bot.filtro)
    assert "Use assim" in mensagem.ultima["texto"]


def test_limite_de_filtros(limpo, monkeypatch):
    criar_usuario(CHAT)
    monkeypatch.setattr(bot.get_settings(), "max_filtros_free", 1)
    mensagem, _ = _rodar(bot.filtro, "professor")
    assert mensagem.ultima["texto"] == textos.limite_filtros(1)


def test_comando_sem_cadastro(limpo):
    mensagem, _ = _rodar(bot.filtros)
    assert mensagem.ultima["texto"] == textos.NAO_CADASTRADO


# ------------------------------ direitos do titular ------------------------------
def test_meus_dados_envia_json(limpo):
    criar_usuario(CHAT, palavras="professor")
    mensagem, _ = _rodar(bot.meus_dados)
    arquivo = mensagem.ultima
    assert arquivo["filename"] == "meus-dados-radar-concurso.json"
    dados = json.loads(arquivo["document"].getvalue())
    assert dados["usuario"]["telegram_chat_id"] == CHAT


def test_meus_dados_sem_cadastro(limpo):
    mensagem, _ = _rodar(bot.meus_dados)
    assert mensagem.ultima["texto"] == textos.SEM_DADOS


def test_apagar_pede_confirmacao_e_apaga(limpo):
    criar_usuario(CHAT)
    mensagem, _ = _rodar(bot.apagar)
    assert _botoes(mensagem.ultima) == [bot.APAGAR_CONFIRMA, bot.APAGAR_CANCELA]

    _, query = _rodar(bot.botao, callback=bot.APAGAR_CANCELA)
    assert query.editado == textos.APAGAR_CANCELADO
    assert _usuarios() == 1

    _, query = _rodar(bot.botao, callback=bot.APAGAR_CONFIRMA)
    assert query.editado == textos.APAGADO
    assert _usuarios() == 0


def test_parar_e_privacidade(limpo):
    criar_usuario(CHAT)
    mensagem, _ = _rodar(bot.parar)
    assert mensagem.ultima["texto"] == textos.PAUSADO
    mensagem, _ = _rodar(bot.privacidade)
    assert "/apagar" in mensagem.ultima["texto"]


def test_botao_acompanhar(limpo):
    mensagem_sem_cadastro = _rodar(bot.botao, callback="acompanhar:1")[1].respostas
    assert mensagem_sem_cadastro == [(textos.NAO_CADASTRADO, True)]

    criar_usuario(CHAT)
    _, query = _rodar(bot.botao, callback="acompanhar:999")
    assert query.respostas == [("Não consegui encontrar esse edital.", True)]


def test_menu_de_comandos_cobre_todos_os_handlers():
    app = bot.criar_app("123:abc")
    registrados = {
        cmd for grupo in app.handlers.values() for h in grupo for cmd in getattr(h, "commands", ())
    }
    assert {nome for nome, _ in textos.COMANDOS} <= registrados
