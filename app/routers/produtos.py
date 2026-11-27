"""Equivalente Python de controller/ProdutoController.java"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_afiliado_id_atual, get_db
from app.schemas.produto import CadastroProdutoRequest, ProdutoResponse
from app.services import produto_service


router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"],
)


@router.get(
    "",
    response_model=list[ProdutoResponse],
)
def listar(
    afiliado: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    com_imagem: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Lista produtos ativos com paginacao.

    Permite filtrar por afiliado e por imagem.
    """

    if afiliado is not None:
        return produto_service.listar_por_afiliado(
            db,
            afiliado,
            limit=limit,
            offset=offset,
            com_imagem=com_imagem,
        )

    return produto_service.listar_todos(
        db,
        limit=limit,
        offset=offset,
        com_imagem=com_imagem,
    )


@router.get(
    "/buscar",
    response_model=list[ProdutoResponse],
)
def buscar(
    q: str = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    com_imagem: bool = Query(default=False),
    mercado: Optional[str] = Query(default=None, max_length=100),
    categoria: Optional[str] = Query(default=None, max_length=100),
    preco_min: Optional[float] = Query(default=None, ge=0),
    preco_max: Optional[float] = Query(default=None, ge=0),
    ordem: str = Query(default="menor", pattern="^(menor|maior|nome)$"),
    db: Session = Depends(get_db),
):
    """
    Busca produtos por nome ou tag com paginacao.
    """

    return produto_service.buscar(
        db,
        q,
        limit=limit,
        offset=offset,
        com_imagem=com_imagem, mercado=mercado, categoria=categoria,
        preco_min=preco_min, preco_max=preco_max, ordem=ordem,
    )


@router.get(
    "/comparar",
    response_model=list[ProdutoResponse],
)
def comparar(
    nome: str = Query(...),
    db: Session = Depends(get_db),
):
    return produto_service.comparar(
        db,
        nome,
    )

@router.get("/sugestoes", response_model=list[str])
def sugestoes(q: str = Query(..., max_length=200), limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)):
    return produto_service.sugestoes(db, q, limit)


@router.get("/{produto_id}/comparacao", response_model=list[ProdutoResponse])
def comparar_por_id(produto_id: int, db: Session = Depends(get_db)):
    return produto_service.comparar_por_id(db, produto_id)


@router.get(
    "/{produto_id}",
    response_model=ProdutoResponse,
)
def buscar_por_id(
    produto_id: int,
    db: Session = Depends(get_db),
):
    """
    Retorna um produto especifico pelo ID.
    """

    return produto_service.buscar_por_id(
        db,
        produto_id,
    )


@router.post(
    "",
    response_model=ProdutoResponse,
    status_code=status.HTTP_201_CREATED,
)
def cadastrar(
    req: CadastroProdutoRequest,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    return produto_service.cadastrar(
        db,
        req,
        afiliado_id,
    )


@router.put(
    "/{produto_id}",
    response_model=ProdutoResponse,
)
def atualizar(
    produto_id: int,
    req: CadastroProdutoRequest,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    return produto_service.atualizar(
        db,
        produto_id,
        req,
        afiliado_id,
    )


@router.delete(
    "/{produto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deletar(
    produto_id: int,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    produto_service.deletar(
        db,
        produto_id,
        afiliado_id,
    )