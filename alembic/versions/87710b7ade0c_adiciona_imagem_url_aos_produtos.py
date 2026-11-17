
"""adiciona imagem_url aos produtos

Revision ID: 87710b7ade0c
Revises: 0004
Create Date: 2026-11-17 16:09:26.201868

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificadores da migração Alembic
revision: str = "87710b7ade0c"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona o campo imagem_url à tabela produtos."""

    op.add_column(
        "produtos",
        sa.Column(
            "imagem_url",
            sa.String(length=2048),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove o campo imagem_url da tabela produtos."""

    op.drop_column(
        "produtos",
        "imagem_url",
    )
