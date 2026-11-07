"""Configuração de logs para todos os processos (worker, bot, api).

LOG_FORMAT=json  -> uma linha JSON por evento (produção: CloudWatch, Loki, Datadog indexam direto)
LOG_FORMAT=texto -> formato legível para desenvolvimento (padrão)

Campos extras vão no `extra=`:  log.info("coleta concluída", extra={"fonte": "dodf", "novos": 3})
Nunca registre dados pessoais (chat_id, e-mail) em logs: veja docs/PRIVACIDADE.md, item 6.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Atributos padrão do LogRecord; tudo o que não estiver aqui veio de `extra=`.
_PADRAO = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

_RUIDOSOS = ("httpx", "httpcore", "telegram", "apscheduler", "uvicorn.access")


def _extras(registro: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in registro.__dict__.items() if k not in _PADRAO and not k.startswith("_")}


class FormatoJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        evento: dict[str, Any] = {
            "ts": datetime.fromtimestamp(registro.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": registro.levelname,
            "logger": registro.name,
            "msg": registro.getMessage(),
            **_extras(registro),
        }
        if registro.exc_info:
            evento["exc"] = self.formatException(registro.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


class FormatoTexto(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def format(self, registro: logging.LogRecord) -> str:
        base = super().format(registro)
        extras = _extras(registro)
        if extras:
            base += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def configurar_logs(formato: str = "texto", nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatoJson() if formato == "json" else FormatoTexto())
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(nivel.upper())
    for nome in _RUIDOSOS:
        logging.getLogger(nome).setLevel(logging.WARNING)
