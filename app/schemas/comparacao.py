from decimal import Decimal
from pydantic import BaseModel, Field


class PrecoLojaResponse(BaseModel):
    loja: str
    preco: Decimal
    imagemUrl: str | None = None
    imagensUrls: list[str] = Field(default_factory=list)


class ComparacaoResponse(BaseModel):
    produto: str
    precos: list[PrecoLojaResponse]
    menor_preco: Decimal
    maior_preco: Decimal
    melhores_lojas: list[str]
    economia: Decimal
    percentual_economia: Decimal
    imagemUrl: str | None = None
    imagensUrls: list[str] = Field(default_factory=list)
