"""Textos do bot (HTML do Telegram). Mudanças na política de privacidade exigem subir
radar.usuarios.TERMOS_VERSAO e atualizar docs/PRIVACIDADE.md."""

from html import escape

from radar.bot.comandos import AJUDA_FILTRO

COMANDOS = [
    ("filtro", "Criar um filtro de concursos"),
    ("filtros", "Ver seus filtros"),
    ("remover", "Apagar um filtro"),
    ("parar", "Pausar os alertas"),
    ("privacidade", "Como tratamos seus dados"),
    ("meusdados", "Baixar todos os seus dados"),
    ("apagar", "Apagar sua conta e todos os dados"),
    ("ajuda", "Ajuda"),
]

BOAS_VINDAS = (
    "👋 <b>Bem-vindo ao Radar Concurso!</b>\n\n"
    "Eu leio o DOU e o DODF todos os dias e te aviso quando sair concurso para o seu perfil.\n\n"
    "Crie seu primeiro filtro:\n" + AJUDA_FILTRO + "\n\n"
    "Outros comandos:\n"
    "/filtros – ver seus filtros\n"
    "/remover &lt;número&gt; – apagar um filtro\n"
    "/parar – pausar os alertas\n"
    "/privacidade – como tratamos seus dados\n"
    "/ajuda – esta mensagem"
)

TERMOS_RESUMO = (
    "🔒 <b>Antes de começar: seus dados</b>\n\n"
    "Para te mandar alertas, eu guardo apenas:\n"
    "• o identificador desta conversa no Telegram (não seu nome nem telefone);\n"
    "• os filtros que você criar;\n"
    "• os editais que você acompanhar e os alertas que te enviei.\n\n"
    "Uso isso <b>só</b> para enviar os alertas. Não vendo nem compartilho seus dados.\n"
    "Você pode baixar tudo (/meusdados) ou apagar tudo (/apagar) quando quiser. "
    "Se você bloquear o bot ou pausar os alertas, apago seus dados após 180 dias.\n\n"
    "Toque em <b>Aceito</b> para continuar."
)

ACEITO = "✅ Aceito"
LER_POLITICA = "📄 Ler a política completa"


def privacidade(contato: str | None) -> str:
    linhas = [
        "🔒 <b>Privacidade no Radar Concurso</b>\n",
        "<b>O que guardo:</b> identificador da conversa no Telegram, seus filtros, editais "
        "acompanhados, alertas enviados e a data em que você aceitou estes termos.",
        "<b>Para quê:</b> exclusivamente para te enviar alertas de concursos.",
        "<b>Base legal:</b> seu consentimento (LGPD, art. 7º, I), que você pode retirar a qualquer momento.",
        "<b>Compartilhamento:</b> nenhum. Seus dados não são vendidos nem cedidos.",
        "<b>Retenção:</b> enquanto você usar o serviço; 180 dias após bloquear o bot ou pausar os "
        "alertas, tudo é apagado automaticamente.",
        "\n<b>Seus direitos:</b>",
        "/meusdados – receber uma cópia de tudo",
        "/apagar – apagar sua conta e todos os dados agora",
        "/parar – parar de receber alertas",
    ]
    if contato:
        linhas.append(f"\nDúvidas: {escape(contato)}")
    return "\n".join(linhas)


CONFIRMAR_APAGAR = (
    "⚠️ <b>Apagar sua conta?</b>\n\n"
    "Vou apagar <b>definitivamente</b> seus filtros, editais acompanhados e histórico de alertas. "
    "Não dá para desfazer."
)
APAGAR_SIM = "🗑 Sim, apagar tudo"
APAGAR_NAO = "Cancelar"
APAGADO = "Pronto: seus dados foram apagados. Se quiser voltar um dia, é só mandar /start. 👋"
APAGAR_CANCELADO = "Ok, nada foi apagado."
SEM_DADOS = "Não tenho nenhum dado seu guardado."

NAO_CADASTRADO = "Mande /start primeiro."
PAUSADO = (
    "⏸ Alertas pausados. Mande /start quando quiser voltar.\n"
    "Se não voltar em 180 dias, seus dados serão apagados automaticamente."
)
TERMOS_ACEITOS = "Obrigado! ✅"


def limite_filtros(total: int) -> str:
    return (
        f"Você já tem {total} filtros, o máximo do plano gratuito. "
        "Apague um com /remover ou aguarde o plano Premium. 😉"
    )
