"""schema inicial — usuarios, afiliados, produtos, contatos, lista_itens

Revision ID: 0001
Revises:
Create Date: 2026-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("senha", sa.String(length=255), nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=True),
        sa.Column("perfil", sa.String(length=20), nullable=False, server_default="CLIENTE"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uk_usuarios_email"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    op.create_table(
        "afiliados",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome_proprietario", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("senha", sa.String(length=255), nullable=False),
        sa.Column("cnpj", sa.String(length=18), nullable=False),
        sa.Column("endereco", sa.String(length=200), nullable=True),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("mercado", sa.String(length=150), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=True),
        sa.Column("funcionarios", sa.Integer(), nullable=True),
        sa.Column("pagamento", sa.String(length=200), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uk_afiliados_email"),
        sa.UniqueConstraint("cnpj", name="uk_afiliados_cnpj"),
    )
    op.create_index("ix_afiliados_email", "afiliados", ["email"])

    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome_produto", sa.String(length=150), nullable=False),
        sa.Column("tags", sa.String(length=500), nullable=True),
        sa.Column("preco", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("afiliado_id", sa.Integer(), sa.ForeignKey("afiliados.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_produtos_nome_produto", "produtos", ["nome_produto"])

    op.create_table(
        "contatos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("mensagem", sa.String(length=2000), nullable=False),
        sa.Column("lido", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "lista_itens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("usuario_id", "produto_id", name="uk_lista_itens_usuario_produto"),
    )


def downgrade() -> None:
    op.drop_table("lista_itens")
    op.drop_table("contatos")
    op.drop_index("ix_produtos_nome_produto", table_name="produtos")
    op.drop_table("produtos")
    op.drop_index("ix_afiliados_email", table_name="afiliados")
    op.drop_table("afiliados")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
