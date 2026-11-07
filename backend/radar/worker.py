"""Worker: coleta -> processamento com IA -> envio de alertas.

Uso:
    python -m radar.worker loop                       # roda para sempre (produção)
    python -m radar.worker ciclo                      # uma rodada completa
    python -m radar.worker coletar --fonte dodf --data 2026-11-06
    python -m radar.worker processar
    python -m radar.worker notificar
"""

import argparse
import logging
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from radar.collectors import criar_coletores
from radar.config import get_settings
from radar.notify.telegram import Telegram, enviar_pendentes
from radar.pipeline.extractor import Extrator
from radar.pipeline.processor import coletar_fonte, processar_pendentes
from radar.usuarios import purgar_inativos

log = logging.getLogger("radar.worker")
FUSO = ZoneInfo("America/Sao_Paulo")


def hoje() -> date:
    return datetime.now(FUSO).date()


def coletar(fonte: str | None = None, dia: date | None = None) -> None:
    settings = get_settings()
    for coletor in criar_coletores(settings):
        if fonte and coletor.fonte != fonte:
            continue
        coletar_fonte(coletor, dia or hoje())


def processar() -> None:
    settings = get_settings()
    n = processar_pendentes(Extrator(settings), settings.max_tentativas)
    log.info("processadas: %s publicações", n)


def notificar() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN não configurado: alertas ficam pendentes")
        return
    enviar_pendentes(Telegram(settings.telegram_bot_token), settings.max_tentativas)


def ciclo() -> None:
    inicio = time.monotonic()
    coletar()
    processar()
    notificar()
    aplicar_retencao()
    log.info("ciclo concluído em %.1fs", time.monotonic() - inicio)


def aplicar_retencao() -> None:
    apagados = purgar_inativos()
    if apagados:
        log.info("retenção LGPD: %s usuários inativos apagados", apagados)


def loop() -> None:
    intervalo = get_settings().intervalo_coleta_min * 60
    while True:
        inicio = time.monotonic()
        try:
            ciclo()
        except Exception:
            log.exception("ciclo falhou; tentando de novo no próximo intervalo")
        time.sleep(max(30.0, intervalo - (time.monotonic() - inicio)))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(prog="radar.worker")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_coletar = sub.add_parser("coletar")
    p_coletar.add_argument("--fonte", choices=["dodf", "dou"])
    p_coletar.add_argument("--data", type=date.fromisoformat, help="AAAA-MM-DD (padrão: hoje)")
    sub.add_parser("processar")
    sub.add_parser("notificar")
    sub.add_parser("ciclo")
    sub.add_parser("loop")
    args = parser.parse_args()

    if args.comando == "coletar":
        coletar(args.fonte, args.data)
    else:
        {"processar": processar, "notificar": notificar, "ciclo": ciclo, "loop": loop}[args.comando]()


if __name__ == "__main__":
    main()
