"""schema inicial: publicações, editais, usuários, filtros e alertas

Revision ID: 0001_schema_inicial
Revises:
Create Date: 2026-11-07
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_schema_inicial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL = Path(__file__).resolve().parent.parent / "sql" / "0001_schema_inicial.sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    # Extensões ficam: podem ser usadas por outros schemas do mesmo banco.
    op.execute(
        "DROP TABLE IF EXISTS coletas, alertas, acompanhamentos, filtros, usuarios, "
        "cargos, editais, publicacoes CASCADE"
    )
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS pt")
