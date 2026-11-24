"""Armazena URLs de todas as imagens fornecidas pelo catalogo do produto."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("produtos", sa.Column("imagem_url", sa.String(length=2048), nullable=True))
    op.add_column("produtos", sa.Column("imagens_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column("produtos", "imagens_urls", server_default=None)


def downgrade():
    op.drop_column("produtos", "imagens_urls")
    op.drop_column("produtos", "imagem_url")
