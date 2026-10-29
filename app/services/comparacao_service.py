"""Comparacao de precos entre mercados cadastrados e lojas externas ativas."""
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.afiliado import Afiliado
from app.models.loja_externa import LojaExterna
from app.models.produto import Produto
from app.schemas.comparacao import (
    ComparacaoResponse,
    PrecoLojaResponse,
)


def _identidade_loja(produto: Produto) -> tuple[str, str] | None:
    """Retorna uma chave unica por estabelecimento e seu nome de exibicao."""
    if produto.afiliado is not None and produto.afiliado.ativo:
        return (f"afiliado:{produto.afiliado.id}", produto.afiliado.mercado)
    if produto.loja_externa is not None and produto.loja_externa.ativo:
        return (f"externa:{produto.loja_externa.id}", produto.loja_externa.nome)
    return None


def comparar_produtos(db: Session, termo: str) -> list[ComparacaoResponse]:
    stmt = (
        select(Produto)
        .options(
            joinedload(Produto.afiliado),
            joinedload(Produto.loja_externa),
        )
        .where(
            Produto.ativo.is_(True),
            or_(
                Produto.afiliado.has(Afiliado.ativo.is_(True)),
                Produto.loja_externa.has(LojaExterna.ativo.is_(True)),
            ),
        )
        .order_by(func.lower(func.trim(Produto.nome_produto)), Produto.preco.asc())
    )
    if termo and termo.strip():
        stmt = stmt.where(Produto.nome_produto.ilike(f"%{termo.strip()}%"))

    produtos = db.scalars(stmt).unique().all()

    agrupados: dict[str, dict] = {}
    for produto in produtos:
        identidade = _identidade_loja(produto)
        if not identidade:
            continue
        loja_id, nome_loja = identidade
        # DEBUG_LOCAL
        chave = produto.nome_produto.strip().casefold()
        if chave not in agrupados:
            agrupados[chave] = {"nome_original": produto.nome_produto.strip(), "lojas": {}}

        # A identidade usa o ID do estabelecimento, nao apenas o nome:
        # dois lojistas podem ter mercados com o mesmo nome exibido.
        lojas = agrupados[chave]["lojas"]
        if loja_id not in lojas:
            lojas[loja_id] = {"nome": nome_loja, "preco": produto.preco}
        elif produto.preco < lojas[loja_id]["preco"]:
            lojas[loja_id]["preco"] = produto.preco

    resultados = []
    for dados in agrupados.values():
        lojas = dados["lojas"]
        if not lojas:
            continue

        registros_lojas = list(lojas.values())
        precos = [registro["preco"] for registro in registros_lojas]
        menor_preco = min(precos)
        maior_preco = max(precos)
        melhores_lojas = [
            registro["nome"] for registro in registros_lojas
            if registro["preco"] == menor_preco
        ]
        economia = maior_preco - menor_preco
        percentual = (
            (economia / maior_preco) * Decimal("100")
            if maior_preco > 0 else Decimal("0")
        )

        precos_response = [
            PrecoLojaResponse(loja=registro["nome"], preco=registro["preco"])
            for registro in sorted(
                registros_lojas,
                key=lambda item: (item["preco"], item["nome"].casefold()),
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
                percentual_economia=percentual.quantize(Decimal("0.01")),
            )
        )

    resultados.sort(key=lambda item: (-item.economia, item.produto.casefold()))
    return resultados
