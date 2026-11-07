"""alarmes operacionais com estado (abre/resolve) para não repetir avisos

Revision ID: 0003_alarmes
Revises: 0002_lgpd
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_alarmes"
down_revision: str | None = "0002_lgpd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alarmes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chave", sa.Text(), nullable=False),
        sa.Column("severidade", sa.Text(), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("aberto_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolvido_em", sa.DateTime(timezone=True)),
        sa.CheckConstraint("severidade IN ('aviso', 'critico')", name="ck_alarmes_severidade"),
    )
    # No máximo um alarme aberto por chave.
    op.create_index(
        "ux_alarmes_abertos",
        "alarmes",
        ["chave"],
        unique=True,
        postgresql_where=sa.text("resolvido_em IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_alarmes_abertos", table_name="alarmes")
    op.drop_table("alarmes")
