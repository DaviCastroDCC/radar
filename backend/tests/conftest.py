"""Fixtures compartilhadas. O banco de teste (radar_test) é recriado do zero a cada execução
e montado pelas migrations do Alembic, exatamente como em produção."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from radar import db
from radar.config import get_settings
from radar.models import Base

BACKEND = Path(__file__).resolve().parent.parent
URL_BASE = os.environ.get("DATABASE_URL", "postgresql+psycopg://radar:radar@localhost:5432/radar")
SERVIDOR = URL_BASE.rsplit("/", 1)[0]
# Derivado dos models: tabela nova entra na limpeza sem ninguém lembrar de atualizar.
TABELAS = ", ".join(Base.metadata.tables)


def _limpar_caches() -> None:
    for cache in (get_settings, db.get_engine, db._session_factory):
        cache.cache_clear()


def criar_banco_vazio(nome: str) -> Engine:
    """Recria o banco `nome` do zero. Pula (ou falha, no CI) se não houver Postgres."""
    # No CI (RADAR_REQUIRE_DB=1) a falta de banco é erro, não um "skip" silencioso.
    indisponivel = pytest.fail if os.environ.get("RADAR_REQUIRE_DB") == "1" else pytest.skip
    try:
        admin = create_engine(f"{SERVIDOR}/postgres", isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)'))
            c.execute(text(f'CREATE DATABASE "{nome}"'))
        admin.dispose()
    except Exception as e:  # sem Postgres por perto
        indisponivel(f"Postgres indisponível: {e}")
    return create_engine(f"{SERVIDOR}/{nome}")


def alembic_config(engine: Engine, conexao=None) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.attributes["connection"] = conexao
    return cfg


def migrar(engine: Engine, alvo: str = "head") -> None:
    with engine.begin() as conexao:
        command.upgrade(alembic_config(engine, conexao), alvo)


@pytest.fixture(scope="session")
def banco_de_teste():
    engine = criar_banco_vazio("radar_test")
    migrar(engine)
    engine.dispose()

    os.environ["DATABASE_URL"] = f"{SERVIDOR}/radar_test"
    _limpar_caches()
    yield
    os.environ["DATABASE_URL"] = URL_BASE
    _limpar_caches()


@pytest.fixture
def limpo(banco_de_teste):
    """Banco de teste vazio para cada teste que precisa de Postgres."""
    with db.session_scope() as s:
        s.execute(text(f"TRUNCATE {TABELAS} RESTART IDENTITY CASCADE"))
