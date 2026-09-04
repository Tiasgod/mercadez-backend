"""Equivalente Python de controller/ProdutoController.java"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_afiliado_id_atual, get_db
from app.schemas.produto import CadastroProdutoRequest, ProdutoResponse
from app.services import produto_service

router = APIRouter(prefix="/produtos", tags=["Produtos"])


@router.get("", response_model=list[ProdutoResponse])
def listar(afiliado: Optional[int] = Query(default=None), db: Session = Depends(get_db)):
    """
    GET /produtos — lista todos os produtos ativos (publico).
    Aceita ?afiliado=<id> para filtrar por loja.
    """
    if afiliado is not None:
        return produto_service.listar_por_afiliado(db, afiliado)
    return produto_service.listar_todos(db)


@router.get("/buscar", response_model=list[ProdutoResponse])
def buscar(q: str = Query(...), db: Session = Depends(get_db)):
    """GET /produtos/buscar?q=arroz — busca por nome/tag."""
    return produto_service.buscar(db, q)


@router.get("/comparar", response_model=list[ProdutoResponse])
def comparar(nome: str = Query(...), db: Session = Depends(get_db)):
    """GET /produtos/comparar?nome=leite — comparacao de precos entre afiliados."""
    return produto_service.comparar(db, nome)


@router.post("", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED)
def cadastrar(
    req: CadastroProdutoRequest,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    """POST /produtos — cadastra produto. Apenas afiliado autenticado."""
    return produto_service.cadastrar(db, req, afiliado_id)


@router.put("/{produto_id}", response_model=ProdutoResponse)
def atualizar(
    produto_id: int,
    req: CadastroProdutoRequest,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    """PUT /produtos/{id} — atualiza produto, verifica dono pelo JWT."""
    return produto_service.atualizar(db, produto_id, req, afiliado_id)


@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    produto_id: int,
    afiliado_id: int = Depends(get_afiliado_id_atual),
    db: Session = Depends(get_db),
):
    """DELETE /produtos/{id} — soft-delete, verifica dono pelo JWT."""
    produto_service.deletar(db, produto_id, afiliado_id)
