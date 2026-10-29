"""
Modelo NOVO — nao existe no backend Java original.

Implementa /listas (GET, POST, DELETE), que o frontend (listas.html) ja
chama mas que nunca foi implementado no backend. Representa a lista de
compras pessoal de um usuario: uma colecao de produtos que ele salvou
para acompanhar/comparar.

Um mesmo usuario nao pode adicionar o mesmo produto duas vezes na lista
(constraint de unicidade usuario_id + produto_id) — uma segunda tentativa
apenas atualiza a quantidade desejada.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ListaItem(Base):
    __tablename__ = "lista_itens"
    __table_args__ = (
        UniqueConstraint("usuario_id", "produto_id", name="uk_lista_itens_usuario_produto"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    produto: Mapped["Produto"] = relationship()
