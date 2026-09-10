"""Equivalente Python de CadastroProdutoRequest / ProdutoResponse."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CadastroProdutoRequest(BaseModel):
    nomeProduto: str = Field(min_length=2, max_length=150)
    tags: Optional[str] = Field(default=None, max_length=500)
    preco: Decimal = Field(gt=0, description="Preco deve ser maior que zero")
    quantidade: int = Field(ge=0)


class ProdutoResponse(BaseModel):
    id: int
    nomeProduto: str
    tags: Optional[str] = None
    preco: Decimal
    quantidade: int
    mercado: str
    afiliadoId: int
    criadoEm: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, produto) -> "ProdutoResponse":
        return cls(
            id=produto.id,
            nomeProduto=produto.nome_produto,
            tags=produto.tags,
            preco=produto.preco,
            quantidade=produto.quantidade,
            mercado=produto.afiliado.mercado,
            afiliadoId=produto.afiliado_id,
            criadoEm=produto.criado_em,
        )
