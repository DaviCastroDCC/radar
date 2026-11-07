"""Bot do Telegram: cadastro, filtros e acompanhamento de editais.

Rodar: python -m radar.bot.main
"""

import asyncio
import logging
from html import escape

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from radar.bot.comandos import AJUDA_FILTRO, NovoFiltro, parse_filtro
from radar.config import get_settings
from radar.db import session_scope
from radar.models import Acompanhamento, Edital, Filtro, Usuario

log = logging.getLogger("radar.bot")

BOAS_VINDAS = (
    "👋 <b>Bem-vindo ao Radar Concurso!</b>\n\n"
    "Eu leio o DOU e o DODF todos os dias e te aviso quando sair concurso para o seu perfil.\n\n"
    "Crie seu primeiro filtro:\n" + AJUDA_FILTRO + "\n\n"
    "Outros comandos:\n"
    "/filtros – ver seus filtros\n"
    "/remover &lt;número&gt; – apagar um filtro\n"
    "/parar – pausar os alertas\n"
    "/ajuda – esta mensagem"
)


# ---------------------------------------------------------------------------
# Acesso ao banco (síncrono, chamado via asyncio.to_thread)
# ---------------------------------------------------------------------------
def _registrar_usuario(chat_id: int, nome: str | None) -> None:
    with session_scope() as s:
        s.execute(
            insert(Usuario)
            .values(telegram_chat_id=chat_id, nome=nome)
            .on_conflict_do_update(index_elements=["telegram_chat_id"], set_={"ativo": True, "nome": nome})
        )


def _usuario_id(s, chat_id: int) -> int | None:
    return s.scalar(select(Usuario.id).where(Usuario.telegram_chat_id == chat_id))


def _criar_filtro(chat_id: int, filtro: NovoFiltro, limite_free: int) -> str:
    with session_scope() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.telegram_chat_id == chat_id))
        if usuario is None:
            return "Mande /start primeiro."
        total = s.scalar(
            select(func.count()).select_from(Filtro).where(Filtro.usuario_id == usuario.id, Filtro.ativo)
        )
        if usuario.plano == "free" and total >= limite_free:
            return (
                f"Você já tem {total} filtros, o máximo do plano gratuito. "
                "Apague um com /remover ou aguarde o plano Premium. 😉"
            )
        s.add(
            Filtro(
                usuario_id=usuario.id,
                palavras=filtro.palavras,
                ufs=filtro.ufs,
                escolaridades=filtro.escolaridades,
                salario_min=filtro.salario_min,
            )
        )
    return f"✅ Filtro criado: {filtro.descricao()}\n\nVou te avisar assim que sair um edital que combine."


def _listar_filtros(chat_id: int) -> str:
    with session_scope() as s:
        uid = _usuario_id(s, chat_id)
        if uid is None:
            return "Mande /start primeiro."
        filtros = s.scalars(
            select(Filtro).where(Filtro.usuario_id == uid, Filtro.ativo).order_by(Filtro.id)
        ).all()
        if not filtros:
            return "Você ainda não tem filtros.\n\n" + AJUDA_FILTRO
        linhas = ["<b>Seus filtros:</b>"]
        for f in filtros:
            nf = NovoFiltro(f.palavras, list(f.ufs), list(f.escolaridades), f.salario_min)
            linhas.append(f"<b>#{f.id}</b> – {nf.descricao()}")
        linhas.append("\nPara apagar: /remover &lt;número&gt;")
        return "\n".join(linhas)


def _remover_filtro(chat_id: int, filtro_id: int) -> str:
    with session_scope() as s:
        uid = _usuario_id(s, chat_id)
        filtro = s.get(Filtro, filtro_id)
        if uid is None or filtro is None or filtro.usuario_id != uid or not filtro.ativo:
            return "Não achei esse filtro. Veja os seus com /filtros."
        filtro.ativo = False
    return f"🗑 Filtro #{filtro_id} removido."


def _parar(chat_id: int) -> None:
    with session_scope() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.telegram_chat_id == chat_id))
        if usuario:
            usuario.ativo = False


def _acompanhar(chat_id: int, edital_id: int) -> str:
    with session_scope() as s:
        uid = _usuario_id(s, chat_id)
        edital = s.get(Edital, edital_id)
        if uid is None or edital is None:
            return "Não consegui encontrar esse edital."
        s.execute(insert(Acompanhamento).values(usuario_id=uid, edital_id=edital_id).on_conflict_do_nothing())
    return "🔔 Pronto! Vou te avisar de retificações e novidades deste edital."


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def _responder(update: Update, texto: str) -> None:
    await update.effective_message.reply_text(texto, parse_mode=ParseMode.HTML)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await asyncio.to_thread(_registrar_usuario, chat.id, update.effective_user.full_name)
    await _responder(update, BOAS_VINDAS)


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, BOAS_VINDAS)


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
    resposta = await asyncio.to_thread(
        _criar_filtro, update.effective_chat.id, novo, get_settings().max_filtros_free
    )
    await _responder(update, resposta)


async def filtros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, await asyncio.to_thread(_listar_filtros, update.effective_chat.id))


async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = (context.args or [""])[0].lstrip("#")
    if not arg.isdigit():
        await _responder(update, "Use: /remover &lt;número&gt; (veja os números em /filtros)")
        return
    await _responder(update, await asyncio.to_thread(_remover_filtro, update.effective_chat.id, int(arg)))


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.to_thread(_parar, update.effective_chat.id)
    await _responder(update, "⏸ Alertas pausados. Mande /start quando quiser voltar.")


async def botao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    acao, _, valor = (query.data or "").partition(":")
    if acao == "acompanhar" and valor.isdigit():
        texto = await asyncio.to_thread(_acompanhar, update.effective_chat.id, int(valor))
        await query.answer(texto, show_alert=True)
    else:
        await query.answer()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    token = get_settings().telegram_bot_token
    if not token:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN (crie o bot com o @BotFather).")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["ajuda", "help"], ajuda))
    app.add_handler(CommandHandler("filtro", filtro))
    app.add_handler(CommandHandler("filtros", filtros))
    app.add_handler(CommandHandler("remover", remover))
    app.add_handler(CommandHandler("parar", parar))
    app.add_handler(CallbackQueryHandler(botao))
    log.info("bot iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
