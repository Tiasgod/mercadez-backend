"""Equivalente Python de service/ProdutoService.java"""
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload

from app.exceptions import AcessoNegadoException, NaoEncontradoException, NegocioException
from app.models.afiliado import Afiliado
from app.models.produto import Produto
from app.schemas.produto import CadastroProdutoRequest, ProdutoResponse


def cadastrar(db: Session, req: CadastroProdutoRequest, afiliado_id: int) -> ProdutoResponse:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None:
        raise NaoEncontradoException("Afiliado nao encontrado.")

    produto = Produto(
        nome_produto=req.nomeProduto,
        tags=req.tags,
        preco=req.preco,
        quantidade=req.quantidade,
        afiliado_id=afiliado_id,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return ProdutoResponse.de(produto)


def listar_todos(db: Session) -> list[ProdutoResponse]:
    produtos = db.scalars(
        select(Produto).options(joinedload(Produto.afiliado)).where(Produto.ativo.is_(True))
    ).all()
    return [ProdutoResponse.de(p) for p in produtos]


def listar_por_afiliado(db: Session, afiliado_id: int) -> list[ProdutoResponse]:
    produtos = db.scalars(
        select(Produto)
        .options(joinedload(Produto.afiliado))
        .where(Produto.afiliado_id == afiliado_id, Produto.ativo.is_(True))
    ).all()
    return [ProdutoResponse.de(p) for p in produtos]


def buscar(db: Session, termo: str) -> list[ProdutoResponse]:
    if not termo or not termo.strip():
        return listar_todos(db)

    padrao = f"%{termo.lower()}%"
    produtos = db.scalars(
        select(Produto)
        .options(joinedload(Produto.afiliado))
        .where(
            Produto.ativo.is_(True),
            or_(
                Produto.nome_produto.ilike(padrao),
                Produto.tags.ilike(padrao),
            ),
        )
        .order_by(Produto.preco.asc())
    ).all()
    return [ProdutoResponse.de(p) for p in produtos]


def comparar(db: Session, nome: str) -> list[ProdutoResponse]:
    if not nome or not nome.strip():
        raise NegocioException("Informe o nome do produto para comparar.")

    padrao = f"%{nome.lower()}%"
    produtos = db.scalars(
        select(Produto)
        .options(joinedload(Produto.afiliado))
        .where(Produto.ativo.is_(True), Produto.nome_produto.ilike(padrao))
        .order_by(Produto.preco.asc())
    ).all()
    return [ProdutoResponse.de(p) for p in produtos]


def atualizar(db: Session, produto_id: int, req: CadastroProdutoRequest, afiliado_id: int) -> ProdutoResponse:
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise NaoEncontradoException("Produto nao encontrado.")

    if produto.afiliado_id != afiliado_id:
        raise AcessoNegadoException("Voce nao tem permissao para editar este produto.")

    produto.nome_produto = req.nomeProduto
    produto.tags = req.tags
    produto.preco = req.preco
    produto.quantidade = req.quantidade

    db.commit()
    db.refresh(produto)
    return ProdutoResponse.de(produto)


def deletar(db: Session, produto_id: int, afiliado_id: int) -> None:
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise NaoEncontradoException("Produto nao encontrado.")

    if produto.afiliado_id != afiliado_id:
        raise AcessoNegadoException("Voce nao tem permissao para excluir este produto.")

    produto.ativo = False  # soft-delete, igual ao backend Java
    db.commit()
