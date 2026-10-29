"""Schemas de cadastro e resposta de produtos."""

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
    afiliadoId: Optional[int] = None
    criadoEm: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, produto) -> "ProdutoResponse":

        if produto.afiliado is not None:
            mercado = produto.afiliado.mercado

        elif produto.loja_externa is not None:
            mercado = produto.loja_externa.nome

        else:
            mercado = "Mercado não informado"

        return cls(
            id=produto.id,
            nomeProduto=produto.nome_produto,
            tags=produto.tags,
            preco=produto.preco,
            quantidade=produto.quantidade,
            mercado=mercado,
            afiliadoId=produto.afiliado_id,
            criadoEm=produto.criado_em,
        )
