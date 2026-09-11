"""
Regra de negocio do novo recurso /listas.

Nao existe no backend Java. Segue o mesmo estilo dos demais services:
o usuario_id vem sempre do JWT (nunca do body), e um usuario so pode
ver/remover os proprios itens.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.exceptions import AcessoNegadoException, NaoEncontradoException
from app.models.lista import ListaItem
from app.models.produto import Produto
from app.schemas.lista import (
    AdicionarListaRequest,
    EconomiaItemResponse,
    EconomiaListaResponse,
    ListaItemResponse,
)


def _carregar_item(db: Session, item_id: int) -> ListaItem:
    item = db.scalar(
        select(ListaItem)
        .options(joinedload(ListaItem.produto).joinedload(Produto.afiliado))
        .where(ListaItem.id == item_id)
    )
    if item is None:
        raise NaoEncontradoException("Item da lista nao encontrado.")
    return item


def listar(db: Session, usuario_id: int) -> list[ListaItemResponse]:
    itens = db.scalars(
        select(ListaItem)
        .options(joinedload(ListaItem.produto).joinedload(Produto.afiliado))
        .where(ListaItem.usuario_id == usuario_id)
        .order_by(ListaItem.criado_em.desc())
    ).all()
    return [ListaItemResponse.de(item) for item in itens]


def adicionar(db: Session, req: AdicionarListaRequest, usuario_id: int) -> ListaItemResponse:
    produto = db.get(Produto, req.produtoId)
    if produto is None or not produto.ativo:
        raise NaoEncontradoException("Produto nao encontrado.")

    item_existente = db.scalar(
        select(ListaItem).where(
            ListaItem.usuario_id == usuario_id,
            ListaItem.produto_id == req.produtoId,
        )
    )

    if item_existente is not None:
        item_existente.quantidade = req.quantidade
        db.commit()
        db.refresh(item_existente)
        return ListaItemResponse.de(_carregar_item(db, item_existente.id))

    item = ListaItem(usuario_id=usuario_id, produto_id=req.produtoId, quantidade=req.quantidade)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ListaItemResponse.de(_carregar_item(db, item.id))


def calcular_economia(db: Session, usuario_id: int) -> EconomiaListaResponse:
    """
    Para cada item da lista, compara o preco do produto escolhido com o
    menor preco encontrado, entre todos os afiliados ativos, para um
    produto de mesmo nome — e soma a economia possivel na lista inteira.
    """
    itens = db.scalars(
        select(ListaItem)
        .options(joinedload(ListaItem.produto).joinedload(Produto.afiliado))
        .where(ListaItem.usuario_id == usuario_id)
    ).all()

    total_atual = Decimal("0")
    total_otimizado = Decimal("0")
    itens_resposta: list[EconomiaItemResponse] = []

    for item in itens:
        produto_atual = item.produto

        mais_barato = db.scalar(
            select(Produto)
            .options(joinedload(Produto.afiliado))
            .where(
                Produto.ativo.is_(True),
                Produto.nome_produto.ilike(produto_atual.nome_produto),
            )
            .order_by(Produto.preco.asc())
            .limit(1)
        )
        # Se por algum motivo nao achar nenhum ativo (ex: o proprio foi
        # desativado), cai de volta pro produto atual — nao ha economia.
        if mais_barato is None:
            mais_barato = produto_atual

        preco_atual_item = produto_atual.preco * item.quantidade
        preco_otimizado_item = mais_barato.preco * item.quantidade

        total_atual += preco_atual_item
        total_otimizado += preco_otimizado_item

        itens_resposta.append(
            EconomiaItemResponse(
                produtoId=item.produto_id,
                nome=produto_atual.nome_produto,
                quantidade=item.quantidade,
                mercadoAtual=produto_atual.afiliado.mercado if produto_atual.afiliado else produto_atual.loja_externa.nome,
                precoAtual=produto_atual.preco,
                mercadoMaisBarato=mais_barato.afiliado.mercado if mais_barato.afiliado else mais_barato.loja_externa.nome,
                precoMaisBarato=mais_barato.preco,
                economiaItem=preco_atual_item - preco_otimizado_item,
            )
        )

    return EconomiaListaResponse(
        totalAtual=total_atual,
        totalOtimizado=total_otimizado,
        economiaTotal=total_atual - total_otimizado,
        itens=itens_resposta,
    )


def remover(db: Session, item_id: int, usuario_id: int) -> None:
    item = db.get(ListaItem, item_id)
    if item is None:
        raise NaoEncontradoException("Item da lista nao encontrado.")

    if item.usuario_id != usuario_id:
        raise AcessoNegadoException("Voce nao tem permissao para remover este item.")

    db.delete(item)
    db.commit()