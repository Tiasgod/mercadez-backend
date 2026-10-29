"""
Modelo de loja externa.
"""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LojaExterna(Base):
    __tablename__ = "lojas_externas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    nome: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    dominio: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    plataforma: Mapped[str] = mapped_column(
        String(30),
        default="VTEX",
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    produtos: Mapped[list["Produto"]] = relationship(
        back_populates="loja_externa",
    )