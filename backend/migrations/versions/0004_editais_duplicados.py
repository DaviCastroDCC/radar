"""editais duplicados entre fontes (banca + diário oficial)

Revision ID: 0004_duplicatas
Revises: 0003_alarmes
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_duplicatas"
down_revision: str | None = "0003_alarmes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "editais",
        sa.Column("duplicata_de_id", sa.BigInteger(), sa.ForeignKey("editais.id"), nullable=True),
    )
    op.create_index(
        "ix_editais_duplicata_de",
        "editais",
        ["duplicata_de_id"],
        postgresql_where=sa.text("duplicata_de_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_editais_duplicata_de", table_name="editais")
    op.drop_column("editais", "duplicata_de_id")
