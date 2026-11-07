"""Fixtures compartilhadas. O banco de teste (radar_test) é recriado do zero a cada execução."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from radar import db
from radar.config import get_settings

SCHEMA = Path(os.environ.get("RADAR_SCHEMA", "/db/schema.sql"))
URL_BASE = os.environ.get("DATABASE_URL", "postgresql+psycopg://radar:radar@localhost:5432/radar")
TABELAS = "alertas, acompanhamentos, filtros, usuarios, cargos, editais, publicacoes, coletas"


def _limpar_caches() -> None:
    for cache in (get_settings, db.get_engine, db._session_factory):
        cache.cache_clear()


@pytest.fixture(scope="session")
def banco_de_teste():
    servidor = URL_BASE.rsplit("/", 1)[0]
    # No CI (RADAR_REQUIRE_DB=1) a falta de banco é erro, não um "skip" silencioso.
    indisponivel = pytest.fail if os.environ.get("RADAR_REQUIRE_DB") == "1" else pytest.skip
    if not SCHEMA.exists():
        indisponivel(f"schema não encontrado em {SCHEMA}")
    try:
        admin = create_engine(f"{servidor}/postgres", isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            c.execute(text("DROP DATABASE IF EXISTS radar_test WITH (FORCE)"))
            c.execute(text("CREATE DATABASE radar_test"))
    except Exception as e:  # sem Postgres por perto
        indisponivel(f"Postgres indisponível: {e}")

    with create_engine(f"{servidor}/radar_test").begin() as c:
        c.exec_driver_sql(SCHEMA.read_text(encoding="utf-8"))

    os.environ["DATABASE_URL"] = f"{servidor}/radar_test"
    _limpar_caches()
    yield
    os.environ["DATABASE_URL"] = URL_BASE
    _limpar_caches()


@pytest.fixture
def limpo(banco_de_teste):
    """Banco de teste vazio para cada teste que precisa de Postgres."""
    with db.session_scope() as s:
        s.execute(text(f"TRUNCATE {TABELAS} RESTART IDENTITY CASCADE"))
