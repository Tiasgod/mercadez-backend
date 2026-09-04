"""Equivalente Python de controller/AfiliadoController.java"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_afiliado_id_atual, get_db
from app.schemas.afiliado import AfiliadoResponse, CadastroAfiliadoRequest
from app.schemas.usuario import LoginRequest, LoginResponse
from app.services import afiliado_service

router = APIRouter(prefix="/afiliados", tags=["Afiliados"])


@router.post("", response_model=AfiliadoResponse, status_code=status.HTTP_201_CREATED)
def cadastrar(req: CadastroAfiliadoRequest, db: Session = Depends(get_db)):
    """POST /afiliados — cadastro de novo afiliado (lojista)."""
    return afiliado_service.cadastrar(db, req)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """POST /afiliados/login"""
    return afiliado_service.login(db, req)


@router.get("/me", response_model=AfiliadoResponse)
def me(afiliado_id: int = Depends(get_afiliado_id_atual), db: Session = Depends(get_db)):
    """GET /afiliados/me — dados do afiliado logado."""
    return afiliado_service.buscar_por_id(db, afiliado_id)
