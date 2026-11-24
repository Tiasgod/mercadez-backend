from decimal import Decimal
from pydantic import BaseModel, Field


class PrecoOfertaResponse(BaseModel):
    loja: str
    preco: Decimal
    imagemUrl: str | None = None
    imagensUrls: list[str] = Field(default_factory=list)


class OfertaResponse(BaseModel):
    produto: str
    melhor_loja: str
    preco: Decimal
    preco_mais_alto: Decimal
    economia: Decimal
    percentual_economia: Decimal
    precos: list[PrecoOfertaResponse]
    imagemUrl: str | None = None
    imagensUrls: list[str] = Field(default_factory=list)
