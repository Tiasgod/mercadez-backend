from decimal import Decimal

from pydantic import BaseModel


class PrecoOfertaResponse(BaseModel):
    loja: str
    preco: Decimal


class OfertaResponse(BaseModel):
    produto: str
    melhor_loja: str
    preco: Decimal
    preco_mais_alto: Decimal
    economia: Decimal
    percentual_economia: Decimal
    precos: list[PrecoOfertaResponse]