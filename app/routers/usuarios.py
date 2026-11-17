"""Rotas de cadastro, autenticacao e gerenciamento de usuarios."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_claims_atuais, get_db, get_usuario_id_atual
from app.exceptions import AcessoNegadoException
from app.models.usuario import Usuario
from app.schemas.usuario import (
    AtualizarUsuarioRequest,
    CadastroUsuarioRequest,
    LoginRequest,
    LoginResponse,
    UsuarioResponse,
)
from app.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


def _autorizar_proprio_ou_admin(usuario_id: int, claims: dict) -> None:
    if claims.get("perfil") != "ADMIN" and int(claims.get("id", -1)) != usuario_id:
        raise AcessoNegadoException("Voce so pode gerenciar sua propria conta.")


@router.post("/cadastro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def cadastrar(req: CadastroUsuarioRequest, db: Session = Depends(get_db)):
    """POST /usuarios/cadastro — cadastro publico de cliente."""
    return usuario_service.cadastrar(db, req)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """POST /usuarios/login — autenticacao publica."""
    return usuario_service.login(db, req)


@router.get("/me", response_model=UsuarioResponse)
def me(usuario_id: int = Depends(get_usuario_id_atual), db: Session = Depends(get_db)):
    """GET /usuarios/me — dados do usuario autenticado."""
    return usuario_service.buscar_por_id(db, usuario_id)


@router.get("", response_model=list[UsuarioResponse])
def listar(
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """GET /usuarios — lista de usuarios, restrita ao administrador."""
    if claims.get("perfil") != "ADMIN":
        raise AcessoNegadoException("Acesso restrito a administradores.")
    usuarios = db.scalars(select(Usuario).order_by(Usuario.id)).all()
    return [UsuarioResponse.de(usuario) for usuario in usuarios]


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def buscar(
    usuario_id: int,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """GET /usuarios/{id} — proprio cadastro ou consulta administrativa."""
    _autorizar_proprio_ou_admin(usuario_id, claims)
    return usuario_service.buscar_por_id(db, usuario_id)


@router.put("/{usuario_id}", response_model=UsuarioResponse)
def atualizar(
    usuario_id: int,
    req: AtualizarUsuarioRequest,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """PUT /usuarios/{id} — proprio cadastro ou administrador."""
    _autorizar_proprio_ou_admin(usuario_id, claims)
    return usuario_service.atualizar(db, usuario_id, req)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    usuario_id: int,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """DELETE /usuarios/{id} — propria conta ou administrador."""
    _autorizar_proprio_ou_admin(usuario_id, claims)
    usuario_service.deletar(db, usuario_id)
