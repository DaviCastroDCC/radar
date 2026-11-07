"""LGPD: consentimento versionado, data de desativação e remoção do nome

Revision ID: 0002_lgpd
Revises: 0001_schema_inicial
Create Date: 2026-11-07

- termos_aceitos_em / termos_versao: prova do consentimento (art. 8º, §2º: o ônus é nosso).
- desativado_em: base da política de retenção (dados apagados após inatividade).
- nome: removido por minimização (art. 6º, III); nunca foi usado pelo produto.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_lgpd"
down_revision: str | None = "0001_schema_inicial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("termos_aceitos_em", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("termos_versao", sa.Text()))
    op.add_column("usuarios", sa.Column("desativado_em", sa.DateTime(timezone=True)))
    op.execute("UPDATE usuarios SET desativado_em = now() WHERE NOT ativo")
    op.create_index(
        "ix_usuarios_desativados",
        "usuarios",
        ["desativado_em"],
        postgresql_where=sa.text("NOT ativo"),
    )
    op.drop_column("usuarios", "nome")


def downgrade() -> None:
    op.add_column("usuarios", sa.Column("nome", sa.Text()))
    op.drop_index("ix_usuarios_desativados", table_name="usuarios")
    op.drop_column("usuarios", "desativado_em")
    op.drop_column("usuarios", "termos_versao")
    op.drop_column("usuarios", "termos_aceitos_em")
