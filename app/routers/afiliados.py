"""Rotas de cadastro, autenticacao e gerenciamento de afiliados/lojistas."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_afiliado_id_atual, get_claims_atuais, get_db
from app.exceptions import AcessoNegadoException
from app.models.afiliado import Afiliado
from app.schemas.afiliado import (
    AfiliadoResponse,
    AtualizarAfiliadoRequest,
    CadastroAfiliadoRequest,
)
from app.schemas.usuario import LoginRequest, LoginResponse
from app.services import afiliado_service

router = APIRouter(prefix="/afiliados", tags=["Afiliados"])


def _autorizar_proprio_ou_admin(afiliado_id: int, claims: dict) -> None:
    if claims.get("perfil") != "ADMIN" and not (
        claims.get("perfil") == "AFILIADO"
        and int(claims.get("id", -1)) == afiliado_id
    ):
        raise AcessoNegadoException("Voce so pode gerenciar seu proprio cadastro.")


@router.post("", response_model=AfiliadoResponse, status_code=status.HTTP_201_CREATED)
def cadastrar(req: CadastroAfiliadoRequest, db: Session = Depends(get_db)):
    """POST /afiliados — cadastro publico de novo lojista."""
    return afiliado_service.cadastrar(db, req)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """POST /afiliados/login — autenticacao de lojista."""
    return afiliado_service.login(db, req)


@router.get("/me", response_model=AfiliadoResponse)
def me(afiliado_id: int = Depends(get_afiliado_id_atual), db: Session = Depends(get_db)):
    """GET /afiliados/me — dados do lojista autenticado."""
    return afiliado_service.buscar_por_id(db, afiliado_id)


@router.get("", response_model=list[AfiliadoResponse])
def listar(
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """GET /afiliados — lista de lojistas, restrita ao administrador."""
    if claims.get("perfil") != "ADMIN":
        raise AcessoNegadoException("Acesso restrito a administradores.")
    afiliados = db.scalars(select(Afiliado).order_by(Afiliado.id)).all()
    return [AfiliadoResponse.de(afiliado) for afiliado in afiliados]


@router.get("/{afiliado_id}", response_model=AfiliadoResponse)
def buscar(
    afiliado_id: int,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """GET /afiliados/{id} — proprio cadastro ou consulta administrativa."""
    _autorizar_proprio_ou_admin(afiliado_id, claims)
    return afiliado_service.buscar_por_id(db, afiliado_id)


@router.put("/{afiliado_id}", response_model=AfiliadoResponse)
def atualizar(
    afiliado_id: int,
    req: AtualizarAfiliadoRequest,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """PUT /afiliados/{id} — atualiza cadastro do lojista autenticado ou via admin."""
    _autorizar_proprio_ou_admin(afiliado_id, claims)
    return afiliado_service.atualizar(db, afiliado_id, req)


@router.delete("/{afiliado_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    afiliado_id: int,
    claims: dict = Depends(get_claims_atuais),
    db: Session = Depends(get_db),
):
    """DELETE /afiliados/{id} — desativa o lojista e suas ofertas."""
    _autorizar_proprio_ou_admin(afiliado_id, claims)
    afiliado_service.deletar(db, afiliado_id)
