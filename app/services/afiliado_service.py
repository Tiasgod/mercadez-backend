"""Equivalente Python de service/AfiliadoService.java"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.exceptions import CredenciaisInvalidasException, NaoEncontradoException, NegocioException
from app.models.afiliado import Afiliado
from app.schemas.afiliado import AfiliadoResponse, CadastroAfiliadoRequest
from app.schemas.usuario import LoginRequest, LoginResponse


def cadastrar(db: Session, req: CadastroAfiliadoRequest) -> AfiliadoResponse:
    email = req.email.lower()

    if db.scalar(select(Afiliado).where(Afiliado.email == email)) is not None:
        raise NegocioException("Email ja cadastrado.")

    if db.scalar(select(Afiliado).where(Afiliado.cnpj == req.cnpj)) is not None:
        raise NegocioException("CNPJ ja cadastrado.")

    afiliado = Afiliado(
        nome_proprietario=req.nome_proprietario,
        email=email,
        senha=security.hash_senha(req.senha),
        cnpj=req.cnpj,
        endereco=req.endereco,
        telefone=req.telefone,
        mercado=req.mercado,
        categoria=req.categoria,
        funcionarios=req.funcionarios,
        pagamento=req.pagamento,
    )
    db.add(afiliado)
    db.commit()
    db.refresh(afiliado)
    return AfiliadoResponse.de(afiliado)


def login(db: Session, req: LoginRequest) -> LoginResponse:
    email = req.email.lower()
    afiliado = db.scalar(select(Afiliado).where(Afiliado.email == email))

    if afiliado is None or not security.verificar_senha(req.senha, afiliado.senha):
        raise CredenciaisInvalidasException()

    token = security.gerar_token(afiliado.id, afiliado.email, "AFILIADO")
    return LoginResponse(
        token=token,
        tipo="Bearer",
        perfil="AFILIADO",
        id=afiliado.id,
        nome=afiliado.nome_proprietario,
        email=afiliado.email,
    )


def buscar_por_id(db: Session, afiliado_id: int) -> AfiliadoResponse:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None:
        raise NaoEncontradoException("Afiliado nao encontrado.")
    return AfiliadoResponse.de(afiliado)
