"""Garantias das migrations: sobem, descem e batem com os models."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from radar.db import incluir_na_comparacao
from radar.models import Base
from tests.conftest import alembic_config, criar_banco_vazio, migrar


def test_historico_linear_com_uma_unica_head():
    scripts = ScriptDirectory.from_config(alembic_config(engine=None))
    assert len(scripts.get_heads()) == 1, "duas heads: alguém precisa fazer `alembic merge`"


def test_upgrade_downgrade_upgrade():
    engine = criar_banco_vazio("radar_migracoes")
    try:
        migrar(engine)
        with engine.begin() as conexao:
            command.downgrade(alembic_config(engine, conexao), "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        migrar(engine)  # sobe de novo: downgrade não deixou lixo
        assert "editais" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_baseline_adota_banco_criado_antes_do_alembic():
    """Bancos antigos foram criados pelo SQL direto; a 0001 precisa aplicar sem erro neles."""
    engine = criar_banco_vazio("radar_legado")
    try:
        sql = alembic_config(engine).get_main_option("script_location") + "/sql/0001_schema_inicial.sql"
        with engine.begin() as conexao, open(sql, encoding="utf-8") as f:
            conexao.exec_driver_sql(f.read())
        migrar(engine)
    finally:
        engine.dispose()


def test_models_sincronizados_com_as_migrations(banco_de_teste):
    """Se este teste falhar, mudaram um model sem migration (ou o contrário)."""
    from radar.db import get_engine

    with get_engine().connect() as conexao:
        contexto = MigrationContext.configure(
            conexao, opts={"include_object": incluir_na_comparacao, "compare_type": True}
        )
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == []
