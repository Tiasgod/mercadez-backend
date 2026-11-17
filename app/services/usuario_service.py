"""Regras de negocio de usuarios."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.exceptions import (
    CredenciaisInvalidasException,
    NaoEncontradoException,
    NegocioException,
)
from app.models.lista import ListaItem
from app.models.usuario import Usuario
from app.schemas.usuario import (
    AtualizarUsuarioRequest,
    CadastroUsuarioRequest,
    LoginRequest,
    LoginResponse,
    UsuarioResponse,
)


def cadastrar(db: Session, req: CadastroUsuarioRequest) -> UsuarioResponse:
    email = str(req.email).lower()

    if db.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        raise NegocioException("Email ja cadastrado.")

    cpf = req.cpf.strip() if req.cpf else None
    if cpf and db.scalar(select(Usuario).where(Usuario.cpf == cpf)) is not None:
        raise NegocioException("CPF ja cadastrado.")

    usuario = Usuario(
        nome=req.nome.strip(),
        email=email,
        senha=security.hash_senha(req.senha),
        cpf=cpf or None,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return UsuarioResponse.de(usuario)


def login(db: Session, req: LoginRequest) -> LoginResponse:
    email = str(req.email).lower()
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


def atualizar(
    db: Session, usuario_id: int, req: AtualizarUsuarioRequest
) -> UsuarioResponse:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoException("Usuario nao encontrado.")

    dados = req.model_dump(exclude_unset=True)
    if "email" in dados:
        email = str(dados["email"]).lower()
        existente = db.scalar(
            select(Usuario).where(Usuario.email == email, Usuario.id != usuario_id)
        )
        if existente is not None:
            raise NegocioException("Email ja cadastrado.")
        dados["email"] = email

    if "cpf" in dados:
        cpf = dados["cpf"].strip() if dados["cpf"] else None
        if cpf:
            existente = db.scalar(
                select(Usuario).where(Usuario.cpf == cpf, Usuario.id != usuario_id)
            )
            if existente is not None:
                raise NegocioException("CPF ja cadastrado.")
        dados["cpf"] = cpf or None

    if "nome" in dados and dados["nome"] is not None:
        dados["nome"] = dados["nome"].strip()

    if "senha" in dados:
        if dados["senha"]:
            dados["senha"] = security.hash_senha(dados["senha"])
        else:
            dados.pop("senha")

    for campo, valor in dados.items():
        setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return UsuarioResponse.de(usuario)


def deletar(db: Session, usuario_id: int) -> None:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoException("Usuario nao encontrado.")

    # Remove os itens pessoais antes de excluir o usuario, evitando
    # violacao da chave estrangeira em lista_itens.
    db.query(ListaItem).filter(ListaItem.usuario_id == usuario_id).delete(
        synchronize_session=False
    )
    db.delete(usuario)
    db.commit()
