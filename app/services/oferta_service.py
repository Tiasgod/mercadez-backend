"""Monta ofertas a partir da comparacao de precos entre mercados ativos."""
from sqlalchemy.orm import Session

from app.schemas.oferta import OfertaResponse, PrecoOfertaResponse
from app.services.comparacao_service import comparar_produtos


def listar_ofertas(db: Session, limite: int = 20) -> list[OfertaResponse]:
    # Reutiliza as mesmas regras de comparacao para nao mostrar ofertas
    # de afiliados/lojas desativados nem divergencias entre endpoints.
    comparacoes = comparar_produtos(db, "")
    ofertas = []
    for comparacao in comparacoes:
        if len(comparacao.precos) < 2 or comparacao.menor_preco >= comparacao.maior_preco:
            continue
        melhor_loja = comparacao.melhores_lojas[0]
        ofertas.append(
            OfertaResponse(
                produto=comparacao.produto,
                melhor_loja=melhor_loja,
                preco=comparacao.menor_preco,
                preco_mais_alto=comparacao.maior_preco,
                economia=comparacao.economia,
                percentual_economia=comparacao.percentual_economia,
                precos=[
                    PrecoOfertaResponse(loja=item.loja, preco=item.preco)
                    for item in comparacao.precos
                ],
            )
        )
    ofertas.sort(
        key=lambda item: (-item.percentual_economia, -item.economia, item.produto.casefold())
    )
    return ofertas[:limite]
