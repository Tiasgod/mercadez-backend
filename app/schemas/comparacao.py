from decimal import Decimal

from pydantic import BaseModel


class PrecoLojaResponse(BaseModel):
    loja: str
    preco: Decimal


class ComparacaoResponse(BaseModel):
    produto: str
    precos: list[PrecoLojaResponse]

    menor_preco: Decimal
    maior_preco: Decimal

    melhores_lojas: list[str]

    economia: Decimal
    percentual_economia: Decimal