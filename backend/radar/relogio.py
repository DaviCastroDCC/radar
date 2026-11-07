"""Fonte única de "agora" (sempre com fuso, UTC), para facilitar testes e evitar datas ingênuas."""

from datetime import UTC, datetime


def agora() -> datetime:
    return datetime.now(UTC)
