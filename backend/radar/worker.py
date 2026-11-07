"""Worker: coleta -> processamento com IA -> envio de alertas -> retenção -> alarmes.

Uso:
    python -m radar.worker loop                       # roda para sempre (produção)
    python -m radar.worker ciclo                      # uma rodada completa
    python -m radar.worker coletar --fonte dodf --data 2026-11-06
    python -m radar.worker processar
    python -m radar.worker notificar
    python -m radar.worker saude                      # diagnóstico no terminal
"""

import argparse
import logging
import time
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from radar.alarmes import notificador_telegram, sincronizar
from radar.collectors import criar_coletores, fontes_disponiveis
from radar.config import get_settings
from radar.db import session_scope
from radar.logs import configurar_logs
from radar.notify.telegram import Telegram, enviar_pendentes
from radar.pipeline.extractor import Extrator
from radar.pipeline.processor import coletada_recentemente, coletar_fonte, processar_pendentes
from radar.saude import Problema, diagnosticar, problemas_atuais
from radar.usuarios import purgar_inativos

log = logging.getLogger("radar.worker")
FUSO = ZoneInfo("America/Sao_Paulo")


def hoje() -> date:
    return datetime.now(FUSO).date()


def coletar(fonte: str | None = None, dia: date | None = None) -> None:
    """Sem argumentos (ciclo normal), respeita o intervalo próprio de cada fonte (bancas: 30 min)."""
    settings = get_settings()
    manual = fonte is not None or dia is not None
    for coletor in criar_coletores(settings):
        if fonte and coletor.fonte != fonte:
            continue
        intervalo = getattr(coletor, "intervalo_min", None)
        if not manual and intervalo and coletada_recentemente(coletor.fonte, intervalo):
            continue
        coletar_fonte(coletor, dia or hoje())


def processar() -> None:
    settings = get_settings()
    n = processar_pendentes(Extrator(settings), settings.max_tentativas)
    log.info("processamento concluído", extra={"processadas": n})


def notificar() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN não configurado: alertas ficam pendentes")
        return
    enviar_pendentes(Telegram(settings.telegram_bot_token), settings.max_tentativas)


def aplicar_retencao() -> None:
    apagados = purgar_inativos()
    if apagados:
        log.info("retenção LGPD aplicada", extra={"usuarios_apagados": apagados})


ETAPAS: list[tuple[str, Callable[[], None]]] = [
    ("coletar", coletar),
    ("processar", processar),
    ("notificar", notificar),
    ("retencao", aplicar_retencao),
]


def executar_etapas(etapas: list[tuple[str, Callable[[], None]]]) -> list[Problema]:
    """Roda cada etapa isolada: a falha de uma não impede as seguintes."""
    falhas = []
    for nome, etapa in etapas:
        inicio = time.monotonic()
        try:
            etapa()
        except Exception as e:
            log.exception("etapa falhou", extra={"etapa": nome})
            falhas.append(
                Problema(f"etapa_falhou:{nome}", "critico", f"Etapa '{nome}' falhou: {type(e).__name__}: {e}")
            )
        else:
            log.info(
                "etapa concluída", extra={"etapa": nome, "segundos": round(time.monotonic() - inicio, 1)}
            )
    return falhas


def avaliar_alarmes(falhas: list[Problema]) -> None:
    settings = get_settings()
    with session_scope() as s:
        # Só o diagnóstico AO VIVO: incluir os alarmes já abertos impediria que se resolvessem.
        problemas = diagnosticar(s, settings)
    sincronizar(falhas + problemas, notificador_telegram(settings))


def ciclo() -> None:
    inicio = time.monotonic()
    falhas = executar_etapas(ETAPAS)
    try:
        avaliar_alarmes(falhas)
    except Exception:
        log.exception("avaliação de alarmes falhou")
    log.info(
        "ciclo concluído", extra={"segundos": round(time.monotonic() - inicio, 1), "falhas": len(falhas)}
    )


def saude() -> None:
    with session_scope() as s:
        problemas = problemas_atuais(s, get_settings())
    if not problemas:
        print("✅ tudo certo")
    for p in problemas:
        print(f"[{p.severidade}] {p.chave}: {p.mensagem}")


def loop() -> None:
    intervalo = get_settings().intervalo_coleta_min * 60
    while True:
        inicio = time.monotonic()
        try:
            ciclo()
        except Exception:
            log.exception("ciclo falhou; tentando de novo no próximo intervalo")
        time.sleep(max(30.0, intervalo - (time.monotonic() - inicio)))


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    configurar_logs(settings.log_format, settings.log_level)

    parser = argparse.ArgumentParser(prog="radar.worker")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_coletar = sub.add_parser("coletar")
    p_coletar.add_argument("--fonte", choices=fontes_disponiveis())
    p_coletar.add_argument("--data", type=date.fromisoformat, help="AAAA-MM-DD (padrão: hoje)")
    for nome in ("processar", "notificar", "ciclo", "loop", "saude"):
        sub.add_parser(nome)
    args = parser.parse_args(argv)

    if args.comando == "coletar":
        coletar(args.fonte, args.data)
        return
    comandos = {"processar": processar, "notificar": notificar, "ciclo": ciclo, "loop": loop, "saude": saude}
    comandos[args.comando]()


if __name__ == "__main__":
    main()
