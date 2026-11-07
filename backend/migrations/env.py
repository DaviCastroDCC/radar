"""Ambiente do Alembic.

- URL do banco: DATABASE_URL (radar.config), igual ao resto da aplicação.
- Testes podem injetar uma conexão pronta em config.attributes["connection"].
- `alembic revision --autogenerate` compara com radar.models, ignorando objetos que só
  existem no banco (índices GIN, colunas tsv geradas): revise sempre o arquivo gerado.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from radar.config import get_settings
from radar.db import incluir_na_comparacao
from radar.models import Base

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _configurar(**kwargs) -> None:
    context.configure(
        target_metadata=Base.metadata,
        include_object=incluir_na_comparacao,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configurar(url=get_settings().database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _rodar(conexao: Connection) -> None:
    _configurar(connection=conexao)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conexao = config.attributes.get("connection")
    if conexao is not None:
        _rodar(conexao)
        return
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as conexao:
        _rodar(conexao)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
