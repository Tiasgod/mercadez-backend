from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.loja_externa import LojaExterna
from app.models.produto import Produto
from app.schemas.comparacao import (
    ComparacaoResponse,
    PrecoLojaResponse,
)


def comparar_produtos(
    db: Session,
    termo: str,
) -> list[ComparacaoResponse]:

    if not termo or not termo.strip():
        return []

    termo = termo.strip()
    padrao = f"%{termo}%"

    stmt = (
        select(Produto, LojaExterna)
        .join(
            LojaExterna,
            Produto.loja_externa_id == LojaExterna.id,
        )
        .where(
            Produto.ativo.is_(True),
            LojaExterna.ativo.is_(True),
            Produto.nome_produto.ilike(padrao),
        )
        .order_by(
            func.lower(func.trim(Produto.nome_produto)),
            Produto.preco.asc(),
        )
    )

    registros = db.execute(stmt).all()

    agrupados = {}

    for produto, loja in registros:

        nome_normalizado = produto.nome_produto.strip().lower()

        if nome_normalizado not in agrupados:
            agrupados[nome_normalizado] = {
                "nome_original": produto.nome_produto,
                "lojas": {},
            }

        lojas = agrupados[nome_normalizado]["lojas"]

        # Caso exista duplicidade na mesma loja,
        # utilizamos o menor preço.
        if loja.nome not in lojas:
            lojas[loja.nome] = produto.preco
        else:
            lojas[loja.nome] = min(
                lojas[loja.nome],
                produto.preco,
            )

    resultados = []

    for dados in agrupados.values():

        lojas = dados["lojas"]

        if not lojas:
            continue

        precos = list(lojas.values())

        menor_preco = min(precos)
        maior_preco = max(precos)

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

        precos_response = [
            PrecoLojaResponse(
                loja=nome_loja,
                preco=preco,
            )
            for nome_loja, preco in sorted(
                lojas.items(),
                key=lambda item: item[1],
            )
        ]

        resultados.append(
            ComparacaoResponse(
                produto=dados["nome_original"],
                precos=precos_response,
                menor_preco=menor_preco,
                maior_preco=maior_preco,
                melhores_lojas=melhores_lojas,
                economia=economia,
                percentual_economia=percentual_economia.quantize(
                    Decimal("0.01")
                ),
            )
        )

    resultados.sort(
        key=lambda item: (
            -item.economia,
            item.produto.lower(),
        )
    )

    return resultados