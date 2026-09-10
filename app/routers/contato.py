"""Equivalente Python de controller/ContatoController.java"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.contato import ContatoRequest
from app.services import contato_service

router = APIRouter(prefix="/contato", tags=["Contato"])


@router.post("", status_code=status.HTTP_201_CREATED)
def enviar(req: ContatoRequest, db: Session = Depends(get_db)):
    """POST /contato — formulario 'Fale Conosco'."""
    contato_service.enviar(db, req)
