"""
Modelo NOVO — historico de precos.

Cada linha e um "snapshot" do preco de um produto em um momento. E gerado
automaticamente (nunca pelo usuario) sempre que produto_service.atualizar()
muda o preco de um produto, e semeado com o preco atual no momento em que
essa tabela foi criada (ver migration 0002).

Usado para: grafico de tendencia de preco, calculo de economia (comparar
preco pago agora vs. media/menor preco historico) e metricas do dashboard
administrativo.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    produto: Mapped["Produto"] = relationship()
