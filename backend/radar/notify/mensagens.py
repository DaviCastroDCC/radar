"""Texto dos alertas (HTML do Telegram). Sem dependência de banco, para testar fácil."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from html import escape

FONTES = {"dodf": "DODF", "dou": "DOU"}


def reais(valor: Decimal | float | None) -> str | None:
    if valor is None:
        return None
    inteiro, _, centavos = f"{Decimal(str(valor)):,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def data_br(d: date | None) -> str | None:
    return d.strftime("%d/%m/%Y") if d else None


def mensagem_alerta(
    *,
    motivo: str,
    tipo: str,
    titulo: str | None,
    orgao: str | None,
    banca: str | None,
    uf: str | None,
    salario_max: Decimal | float | None,
    vagas_total: int | None,
    inscricao_inicio: date | None,
    inscricao_fim: date | None,
    data_prova: date | None,
    link_inscricao: str | None,
    resumo: str | None,
    cargos_casados: Sequence[str],
    fonte: str,
    data_publicacao: date,
    url_publicacao: str | None,
) -> str:
    if motivo == "retificacao":
        cabecalho = {
            "retificacao": "✏️ <b>Retificação no edital que você acompanha</b>",
            "prorrogacao": "⏳ <b>Inscrições prorrogadas</b>",
            "cancelamento": "⛔ <b>Concurso cancelado/suspenso</b>",
            "resultado": "📊 <b>Saiu resultado</b>",
            "convocacao": "📣 <b>Nova convocação</b>",
            "homologacao": "✅ <b>Resultado final homologado</b>",
        }.get(tipo, "🔔 <b>Novidade no edital que você acompanha</b>")
    else:
        cabecalho = "🚨 <b>Saiu concurso para o seu perfil!</b>"

    linhas = [cabecalho, "", f"<b>{escape(titulo or orgao or 'Concurso')}</b>"]
    if orgao and orgao != titulo:
        linhas.append(f"🏛 {escape(orgao)}" + (f" ({escape(uf)})" if uf else ""))
    if banca:
        linhas.append(f"📝 Banca: {escape(banca)}")
    if cargos_casados:
        lista = ", ".join(cargos_casados[:5])
        extra = f" e mais {len(cargos_casados) - 5}" if len(cargos_casados) > 5 else ""
        linhas.append(f"🎯 Cargos do seu filtro: {escape(lista)}{extra}")
    if vagas_total:
        linhas.append(f"👥 Vagas: {vagas_total}")
    if salario_max:
        linhas.append(f"💰 Até {reais(salario_max)}")
    if inscricao_inicio or inscricao_fim:
        periodo = " a ".join(p for p in (data_br(inscricao_inicio), data_br(inscricao_fim)) if p)
        linhas.append(f"🗓 Inscrições: {periodo}")
    if data_prova:
        linhas.append(f"✍️ Prova: {data_br(data_prova)}")
    if resumo:
        linhas += ["", escape(resumo)]
    if link_inscricao:
        linhas.append(f"\n🔗 Inscrição: {escape(link_inscricao)}")

    origem = f"{FONTES.get(fonte, fonte.upper())} de {data_br(data_publicacao)}"
    if url_publicacao:
        origem = f'<a href="{escape(url_publicacao, quote=True)}">{origem}</a>'
    linhas.append(f"\n📄 Fonte: {origem}")
    return "\n".join(linhas)
