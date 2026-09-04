"""Equivalente Python de model/Produto.java"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, DateTime, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome_produto: Mapped[str] = mapped_column("nome_produto", String(150), nullable=False, index=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    afiliado_id: Mapped[int] = mapped_column(ForeignKey("afiliados.id"), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    afiliado: Mapped["Afiliado"] = relationship(back_populates="produtos")
