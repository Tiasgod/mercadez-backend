"""aumenta tamanho do nome do produto

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "produtos",
        "nome_produto",
        existing_type=sa.String(length=150),
        type_=sa.String(length=500),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "produtos",
        "nome_produto",
        existing_type=sa.String(length=500),
        type_=sa.String(length=150),
        existing_nullable=False,
    )