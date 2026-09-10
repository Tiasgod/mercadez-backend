"""Equivalente Python de controller/UsuarioController.java"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_usuario_id_atual
from app.schemas.usuario import CadastroUsuarioRequest, LoginRequest, LoginResponse, UsuarioResponse
from app.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("/cadastro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def cadastrar(req: CadastroUsuarioRequest, db: Session = Depends(get_db)):
    """POST /usuarios/cadastro — rota publica."""
    return usuario_service.cadastrar(db, req)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """POST /usuarios/login — rota publica."""
    return usuario_service.login(db, req)


@router.get("/me", response_model=UsuarioResponse)
def me(usuario_id: int = Depends(get_usuario_id_atual), db: Session = Depends(get_db)):
    """GET /usuarios/me — requer autenticacao."""
    return usuario_service.buscar_por_id(db, usuario_id)
