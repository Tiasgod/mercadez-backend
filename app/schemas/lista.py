"""
Schemas do novo recurso /listas (lista de compras do usuario).

Nao existe equivalente no backend Java — foi desenhado a partir do
contrato que o frontend (listas.html) ja consome: cada item retorna
como um "produto" com id, nome, preco e quantidade, com categoria/marca
opcionais (o frontend ja trata a ausencia desses dois campos).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class AdicionarListaRequest(BaseModel):
    produtoId: int
    quantidade: int = Field(default=1, ge=1)


class EconomiaItemResponse(BaseModel):
    """Comparacao de 1 item da lista: o que o usuario escolheu vs a opcao
    mais barata disponivel entre todos os afiliados que vendem o mesmo
    produto no momento."""

    produtoId: int
    nome: str
    quantidade: int
    mercadoAtual: str
    precoAtual: Decimal
    mercadoMaisBarato: str
    precoMaisBarato: Decimal
    economiaItem: Decimal


class EconomiaListaResponse(BaseModel):
    """Resumo de economia da lista inteira: quanto custaria do jeito que
    esta montada agora vs. pegando sempre a opcao mais barata por item."""

    totalAtual: Decimal
    totalOtimizado: Decimal
    economiaTotal: Decimal
    itens: list[EconomiaItemResponse]


class ListaItemResponse(BaseModel):
    id: int
    produtoId: int
    nome: str
    mercado: str
    preco: Decimal
    quantidade: int
    categoria: Optional[str] = None
    marca: Optional[str] = None
    criadoEm: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, item) -> "ListaItemResponse":
        return cls(
            id=item.id,
            produtoId=item.produto_id,
            nome=item.produto.nome_produto,
            mercado=item.produto.afiliado.mercado,
            preco=item.produto.preco,
            quantidade=item.quantidade,
            categoria=None,
            marca=None,
            criadoEm=item.criado_em,
        )