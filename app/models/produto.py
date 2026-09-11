"""Modelo SQLAlchemy de Produto."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    nome_produto: Mapped[str] = mapped_column(
        "nome_produto",
        String(150),
        nullable=False,
    )

    tags: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    preco: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    quantidade: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    afiliado_id: Mapped[int | None] = mapped_column(
        ForeignKey("afiliados.id"),
        nullable=True,
        index=True,
    )

    loja_externa_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas_externas.id"),
        nullable=True,
        index=True,
    )

    origem: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="AFILIADO",
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    afiliado: Mapped["Afiliado | None"] = relationship(
        back_populates="produtos",
    )

    loja_externa: Mapped["LojaExterna | None"] = relationship(
        back_populates="produtos",
    )