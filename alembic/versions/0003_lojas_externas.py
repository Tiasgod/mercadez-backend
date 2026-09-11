"""adiciona lojas_externas — fontes de preco externas (ex: Carrefour, Pao
de Acucar) que nao sao afiliados de verdade, so referencia de comparacao

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lojas_externas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(100), nullable=False, unique=True),
        sa.Column("dominio", sa.String(200), nullable=False),
        sa.Column("plataforma", sa.String(30), nullable=False, server_default="VTEX"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # afiliado_id deixa de ser obrigatorio: um produto agora pertence a UM
    # afiliado OU a UMA loja externa, nunca aos dois nem a nenhum.
    op.alter_column("produtos", "afiliado_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "produtos",
        sa.Column("loja_externa_id", sa.Integer(), sa.ForeignKey("lojas_externas.id"), nullable=True),
    )
    op.add_column(
        "produtos",
        sa.Column("origem", sa.String(20), nullable=False, server_default="AFILIADO"),
    )
    op.create_check_constraint(
        "ck_produtos_exatamente_um_dono",
        "produtos",
        "(afiliado_id IS NOT NULL) <> (loja_externa_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_produtos_exatamente_um_dono", "produtos", type_="check")
    op.drop_column("produtos", "origem")
    op.drop_column("produtos", "loja_externa_id")
    op.alter_column("produtos", "afiliado_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("lojas_externas")