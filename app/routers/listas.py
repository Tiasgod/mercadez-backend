"""
Router NOVO: /listas — nao existe no backend Java.

O frontend (listas.html) ja chama GET /listas e DELETE /listas/{id},
mas o endpoint nunca existiu no backend, entao a pagina falhava
silenciosamente. Este router implementa o recurso de verdade,
incluindo POST /listas para adicionar itens (necessario para a
lista ter conteudo).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_usuario_id_atual
from app.schemas.lista import AdicionarListaRequest, ListaItemResponse
from app.services import lista_service

router = APIRouter(prefix="/listas", tags=["Listas"])


@router.get("", response_model=list[ListaItemResponse])
def listar(usuario_id: int = Depends(get_usuario_id_atual), db: Session = Depends(get_db)):
    """GET /listas — itens da lista de compras do usuario logado."""
    return lista_service.listar(db, usuario_id)


@router.post("", response_model=ListaItemResponse, status_code=status.HTTP_201_CREATED)
def adicionar(
    req: AdicionarListaRequest,
    usuario_id: int = Depends(get_usuario_id_atual),
    db: Session = Depends(get_db),
):
    """POST /listas — adiciona um produto a lista do usuario logado."""
    return lista_service.adicionar(db, req, usuario_id)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    item_id: int,
    usuario_id: int = Depends(get_usuario_id_atual),
    db: Session = Depends(get_db),
):
    """DELETE /listas/{id} — remove um item da lista do usuario logado."""
    lista_service.remover(db, item_id, usuario_id)
