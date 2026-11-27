"""Indices de busca sem acentos e comparacao exata."""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    expr = "translate(lower(nome_produto), 'áàâãäéèêëíìîïóòôõöúùûüçñýÿ', 'aaaaaeeeeiiiiooooouuuucnyy')"
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_produtos_busca_nome ON produtos USING gin (({expr}) gin_trgm_ops) WHERE ativo IS TRUE")
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_produtos_comparacao_nome ON produtos (trim({expr})) WHERE ativo IS TRUE")
    tags = expr.replace("nome_produto", "tags")
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_produtos_busca_tags ON produtos USING gin (({tags}) gin_trgm_ops) WHERE ativo IS TRUE")


def downgrade():
    for nome in ("ix_produtos_busca_tags", "ix_produtos_comparacao_nome", "ix_produtos_busca_nome"):
        op.execute(f"DROP INDEX IF EXISTS {nome}")
