"""adiciona historico_precos — registra cada mudanca de preco de um produto

Necessario para: comparacao de economia ao longo do tempo, grafico de
tendencia de preco e o dashboard administrativo (item 1/2/3 do roadmap
de evolucao do backend).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historico_precos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("preco", sa.Numeric(10, 2), nullable=False),
        sa.Column("registrado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_historico_precos_produto_data",
        "historico_precos",
        ["produto_id", "registrado_em"],
    )

    # Semeia o historico com o preco atual de cada produto ja cadastrado,
    # para que produtos existentes ja tenham pelo menos 1 ponto na serie.
    op.execute(
        """
        INSERT INTO historico_precos (produto_id, preco, registrado_em)
        SELECT id, preco, atualizado_em FROM produtos
        """
    )


def downgrade() -> None:
    op.drop_index("ix_historico_precos_produto_data", table_name="historico_precos")
    op.drop_table("historico_precos")
