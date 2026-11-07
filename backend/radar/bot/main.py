"""Bot do Telegram: casca fina sobre radar.usuarios. Aqui só há I/O com o Telegram.

Rodar: python -m radar.bot.main
"""

import asyncio
import io
import json
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from html import escape

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from radar import usuarios
from radar.bot import textos
from radar.bot.comandos import AJUDA_FILTRO, NovoFiltro, parse_filtro
from radar.config import get_settings
from radar.logs import configurar_logs

log = logging.getLogger("radar.bot")

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]

# callback_data dos botões
ACEITAR_TERMOS = "termos:aceitar"
APAGAR_CONFIRMA = "apagar:sim"
APAGAR_CANCELA = "apagar:nao"
ACOMPANHAR = "acompanhar"


async def _responder(update: Update, texto: str, teclado: InlineKeyboardMarkup | None = None) -> None:
    await update.effective_message.reply_text(
        texto, parse_mode=ParseMode.HTML, reply_markup=teclado, disable_web_page_preview=True
    )


def _teclado_termos() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(textos.ACEITO, callback_data=ACEITAR_TERMOS)],
            [InlineKeyboardButton(textos.LER_POLITICA, url=get_settings().url_politica_privacidade)],
        ]
    )


async def _pedir_termos(update: Update) -> None:
    await _responder(update, textos.TERMOS_RESUMO, _teclado_termos())


def tratando_erros_de_usuario(handler: Handler) -> Handler:
    """Converte as regras de negócio violadas em mensagens amigáveis."""

    @wraps(handler)
    async def envolvido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await handler(update, context)
        except usuarios.UsuarioNaoCadastrado:
            await _responder(update, textos.NAO_CADASTRADO)
        except usuarios.TermosPendentes:
            await _pedir_termos(update)
        except usuarios.LimiteDeFiltros as e:
            await _responder(update, textos.limite_filtros(e.total))

    return envolvido


def _chat(update: Update) -> int:
    return update.effective_chat.id


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ja_aceitou = await asyncio.to_thread(usuarios.registrar, _chat(update))
    if ja_aceitou:
        await _responder(update, textos.BOAS_VINDAS)
    else:
        await _pedir_termos(update)


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, textos.BOAS_VINDAS)


@tratando_erros_de_usuario
async def filtro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = " ".join(context.args or [])
    if not texto:
        await _responder(update, AJUDA_FILTRO)
        return
    try:
        novo = parse_filtro(texto)
    except ValueError as e:
        await _responder(update, f"⚠️ {escape(str(e))}\n\n{AJUDA_FILTRO}")
        return
    filtro_id = await asyncio.to_thread(
        usuarios.criar_filtro,
        _chat(update),
        palavras=novo.palavras,
        ufs=novo.ufs,
        escolaridades=novo.escolaridades,
        salario_min=novo.salario_min,
        limite_free=get_settings().max_filtros_free,
    )
    await _responder(
        update,
        f"✅ Filtro #{filtro_id} criado: {novo.descricao()}\n\n"
        "Vou te avisar assim que sair um edital que combine.",
    )


@tratando_erros_de_usuario
async def filtros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lista = await asyncio.to_thread(usuarios.listar_filtros, _chat(update))
    if not lista:
        await _responder(update, "Você ainda não tem filtros.\n\n" + AJUDA_FILTRO)
        return
    linhas = ["<b>Seus filtros:</b>"]
    for f in lista:
        desc = NovoFiltro(f.palavras, f.ufs, f.escolaridades, f.salario_min).descricao()
        linhas.append(f"<b>#{f.id}</b> – {desc}")
    linhas.append("\nPara apagar: /remover &lt;número&gt;")
    await _responder(update, "\n".join(linhas))


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = (context.args or [""])[0].lstrip("#")
    if not arg.isdigit():
        await _responder(update, "Use: /remover &lt;número&gt; (veja os números em /filtros)")
        return
    removido = await asyncio.to_thread(usuarios.remover_filtro, _chat(update), int(arg))
    await _responder(
        update,
        f"🗑 Filtro #{arg} removido." if removido else "Não achei esse filtro. Veja os seus com /filtros.",
    )


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.to_thread(usuarios.pausar, _chat(update))
    await _responder(update, textos.PAUSADO)


async def privacidade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, textos.privacidade(get_settings().contato_privacidade), _teclado_termos_link())


def _teclado_termos_link() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(textos.LER_POLITICA, url=get_settings().url_politica_privacidade)]]
    )


async def meus_dados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dados = await asyncio.to_thread(usuarios.exportar_dados, _chat(update))
    if dados is None:
        await _responder(update, textos.SEM_DADOS)
        return
    arquivo = io.BytesIO(json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8"))
    await update.effective_message.reply_document(
        document=arquivo,
        filename="meus-dados-radar-concurso.json",
        caption="📦 Aqui está tudo o que guardo sobre você.",
    )


async def apagar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    teclado = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(textos.APAGAR_SIM, callback_data=APAGAR_CONFIRMA)],
            [InlineKeyboardButton(textos.APAGAR_NAO, callback_data=APAGAR_CANCELA)],
        ]
    )
    await _responder(update, textos.CONFIRMAR_APAGAR, teclado)


# ---------------------------------------------------------------------------
# Botões
# ---------------------------------------------------------------------------
async def botao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    dado = query.data or ""
    chat_id = _chat(update)

    if dado == ACEITAR_TERMOS:
        await asyncio.to_thread(usuarios.registrar, chat_id)
        await asyncio.to_thread(usuarios.aceitar_termos, chat_id)
        await query.answer(textos.TERMOS_ACEITOS)
        await query.edit_message_text(textos.BOAS_VINDAS, parse_mode=ParseMode.HTML)
    elif dado == APAGAR_CONFIRMA:
        apagado = await asyncio.to_thread(usuarios.apagar, chat_id)
        await query.answer()
        await query.edit_message_text(textos.APAGADO if apagado else textos.SEM_DADOS)
    elif dado == APAGAR_CANCELA:
        await query.answer()
        await query.edit_message_text(textos.APAGAR_CANCELADO)
    elif dado.startswith(f"{ACOMPANHAR}:") and dado.partition(":")[2].isdigit():
        await query.answer(await _acompanhar(chat_id, int(dado.partition(":")[2])), show_alert=True)
    else:
        await query.answer()


async def _acompanhar(chat_id: int, edital_id: int) -> str:
    try:
        ok = await asyncio.to_thread(usuarios.acompanhar, chat_id, edital_id)
    except usuarios.UsuarioNaoCadastrado:
        return textos.NAO_CADASTRADO
    except usuarios.TermosPendentes:
        return "Mande /start e aceite os termos para acompanhar editais."
    if not ok:
        return "Não consegui encontrar esse edital."
    return "🔔 Pronto! Vou te avisar de retificações e novidades deste edital."


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
async def _registrar_menu(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand(nome, desc) for nome, desc in textos.COMANDOS])


def criar_app(token: str) -> Application:
    app = Application.builder().token(token).post_init(_registrar_menu).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["ajuda", "help"], ajuda))
    app.add_handler(CommandHandler("filtro", filtro))
    app.add_handler(CommandHandler("filtros", filtros))
    app.add_handler(CommandHandler("remover", remover))
    app.add_handler(CommandHandler("parar", parar))
    app.add_handler(CommandHandler("privacidade", privacidade))
    app.add_handler(CommandHandler("meusdados", meus_dados))
    app.add_handler(CommandHandler("apagar", apagar))
    app.add_handler(CallbackQueryHandler(botao))
    return app


def main() -> None:
    settings = get_settings()
    configurar_logs(settings.log_format, settings.log_level)
    token = settings.telegram_bot_token
    if not token:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN (crie o bot com o @BotFather).")
    log.info("bot iniciado")
    criar_app(token).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
