from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from radar.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


def incluir_na_comparacao(obj, name, type_, reflected, compare_to) -> bool:
    """Filtro do autogenerate do Alembic: ignora objetos que só existem no banco
    (índices GIN, colunas tsv geradas), que são mantidos à mão nas migrations SQL."""
    return not (reflected and compare_to is None)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Abre uma sessão, faz commit no fim ou rollback se algo falhar."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
