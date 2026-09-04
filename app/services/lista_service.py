"""
Regra de negocio do novo recurso /listas.

Nao existe no backend Java. Segue o mesmo estilo dos demais services:
o usuario_id vem sempre do JWT (nunca do body), e um usuario so pode
ver/remover os proprios itens.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.exceptions import AcessoNegadoException, NaoEncontradoException
from app.models.lista import ListaItem
from app.models.produto import Produto
from app.schemas.lista import AdicionarListaRequest, ListaItemResponse


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


def remover(db: Session, item_id: int, usuario_id: int) -> None:
    item = db.get(ListaItem, item_id)
    if item is None:
        raise NaoEncontradoException("Item da lista nao encontrado.")

    if item.usuario_id != usuario_id:
        raise AcessoNegadoException("Voce nao tem permissao para remover este item.")

    db.delete(item)
    db.commit()
