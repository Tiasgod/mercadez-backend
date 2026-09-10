"""Equivalente Python de service/UsuarioService.java"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.exceptions import CredenciaisInvalidasException, NaoEncontradoException, NegocioException
from app.models.usuario import Usuario
from app.schemas.usuario import CadastroUsuarioRequest, LoginRequest, LoginResponse, UsuarioResponse


def cadastrar(db: Session, req: CadastroUsuarioRequest) -> UsuarioResponse:
    email = req.email.lower()

    if db.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        raise NegocioException("Email ja cadastrado.")

    if req.cpf and req.cpf.strip():
        if db.scalar(select(Usuario).where(Usuario.cpf == req.cpf)) is not None:
            raise NegocioException("CPF ja cadastrado.")

    usuario = Usuario(
        nome=req.nome,
        email=email,
        senha=security.hash_senha(req.senha),
        cpf=req.cpf,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return UsuarioResponse.de(usuario)


def login(db: Session, req: LoginRequest) -> LoginResponse:
    email = req.email.lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    if usuario is None or not security.verificar_senha(req.senha, usuario.senha):
        raise CredenciaisInvalidasException()

    token = security.gerar_token(usuario.id, usuario.email, usuario.perfil.value)
    return LoginResponse(
        token=token,
        tipo="Bearer",
        perfil=usuario.perfil.value,
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
    )


def buscar_por_id(db: Session, usuario_id: int) -> UsuarioResponse:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoException("Usuario nao encontrado.")
    return UsuarioResponse.de(usuario)
