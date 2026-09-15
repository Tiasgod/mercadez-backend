from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.loja_externa import LojaExterna
from app.models.produto import Produto
from app.schemas.oferta import (
    OfertaResponse,
    PrecoOfertaResponse,
)


def listar_ofertas(
    db: Session,
    limite: int = 20,
) -> list[OfertaResponse]:

    stmt = (
        select(Produto, LojaExterna)
        .join(
            LojaExterna,
            Produto.loja_externa_id == LojaExterna.id,
        )
        .where(
            Produto.ativo.is_(True),
            LojaExterna.ativo.is_(True),
        )
        .order_by(
            func.lower(func.trim(Produto.nome_produto)),
            Produto.preco.asc(),
        )
    )

    registros = db.execute(stmt).all()

    agrupados = {}

    for produto, loja in registros:

        nome_normalizado = (
            produto.nome_produto.strip().lower()
        )

        if nome_normalizado not in agrupados:
            agrupados[nome_normalizado] = {
                "nome_original": produto.nome_produto,
                "lojas": {},
            }

        lojas = agrupados[nome_normalizado]["lojas"]

        # Se houver mais de um registro do mesmo produto
        # na mesma loja, mantém somente o menor preço.
        if loja.nome not in lojas:
            lojas[loja.nome] = produto.preco
        else:
            lojas[loja.nome] = min(
                lojas[loja.nome],
                produto.preco,
            )

    ofertas = []

    for dados in agrupados.values():

        lojas = dados["lojas"]

        # Para ser uma oferta de comparação,
        # precisamos de pelo menos duas lojas.
        if len(lojas) < 2:
            continue

        menor_preco = min(lojas.values())
        maior_preco = max(lojas.values())

        # Se todas as lojas tiverem o mesmo preço,
        # não existe economia.
        if menor_preco >= maior_preco:
            continue

        melhores_lojas = [
            nome_loja
            for nome_loja, preco in lojas.items()
            if preco == menor_preco
        ]

        economia = maior_preco - menor_preco

        if maior_preco > 0:
            percentual_economia = (
                economia / maior_preco
            ) * Decimal("100")
        else:
            percentual_economia = Decimal("0")

        # Ordena as lojas pelo menor preço.
        precos = [
            PrecoOfertaResponse(
                loja=nome_loja,
                preco=preco,
            )
            for nome_loja, preco in sorted(
                lojas.items(),
                key=lambda item: item[1],
            )
        ]

        # Cada produto pode ter mais de uma loja empatada
        # com o menor preço. A primeira será usada como
        # melhor loja no retorno.
        melhor_loja = melhores_lojas[0]

        ofertas.append(
            OfertaResponse(
                produto=dados["nome_original"],
                melhor_loja=melhor_loja,
                preco=menor_preco,
                preco_mais_alto=maior_preco,
                economia=economia,
                percentual_economia=percentual_economia.quantize(
                    Decimal("0.01")
                ),
                precos=precos,
            )
        )

    # Maior percentual de economia primeiro.
    # Em caso de empate, maior economia em reais.
    ofertas.sort(
        key=lambda item: (
            -item.percentual_economia,
            -item.economia,
            item.produto.lower(),
        )
    )

    return ofertas[:limite]