"""Regras de negocio de afiliados/lojistas."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.exceptions import (
    CredenciaisInvalidasException,
    NaoEncontradoException,
    NegocioException,
)
from app.models.afiliado import Afiliado
from app.models.produto import Produto
from app.schemas.afiliado import (
    AfiliadoResponse,
    AtualizarAfiliadoRequest,
    CadastroAfiliadoRequest,
)
from app.schemas.usuario import LoginRequest, LoginResponse


def cadastrar(db: Session, req: CadastroAfiliadoRequest) -> AfiliadoResponse:
    email = str(req.email).lower()
    cnpj = req.cnpj.strip()

    if db.scalar(select(Afiliado).where(Afiliado.email == email)) is not None:
        raise NegocioException("Email ja cadastrado.")
    if db.scalar(select(Afiliado).where(Afiliado.cnpj == cnpj)) is not None:
        raise NegocioException("CNPJ ja cadastrado.")

    afiliado = Afiliado(
        nome_proprietario=req.nome_proprietario.strip(),
        email=email,
        senha=security.hash_senha(req.senha),
        cnpj=cnpj,
        endereco=req.endereco,
        telefone=req.telefone,
        mercado=req.mercado.strip(),
        categoria=req.categoria,
        funcionarios=req.funcionarios,
        pagamento=req.pagamento,
    )
    db.add(afiliado)
    db.commit()
    db.refresh(afiliado)
    return AfiliadoResponse.de(afiliado)


def login(db: Session, req: LoginRequest) -> LoginResponse:
    email = str(req.email).lower()
    afiliado = db.scalar(select(Afiliado).where(Afiliado.email == email))

    if afiliado is None or not afiliado.ativo or not security.verificar_senha(req.senha, afiliado.senha):
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


def atualizar(
    db: Session, afiliado_id: int, req: AtualizarAfiliadoRequest
) -> AfiliadoResponse:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None:
        raise NaoEncontradoException("Afiliado nao encontrado.")
    if not afiliado.ativo:
        raise NegocioException("Este afiliado esta desativado.")

    dados = req.model_dump(exclude_unset=True)

    if "email" in dados:
        email = str(dados["email"]).lower()
        existente = db.scalar(
            select(Afiliado).where(Afiliado.email == email, Afiliado.id != afiliado_id)
        )
        if existente is not None:
            raise NegocioException("Email ja cadastrado.")
        dados["email"] = email

    if "cnpj" in dados:
        cnpj = dados["cnpj"].strip()
        existente = db.scalar(
            select(Afiliado).where(Afiliado.cnpj == cnpj, Afiliado.id != afiliado_id)
        )
        if existente is not None:
            raise NegocioException("CNPJ ja cadastrado.")
        dados["cnpj"] = cnpj

    if "nome_proprietario" in dados and dados["nome_proprietario"] is not None:
        dados["nome_proprietario"] = dados["nome_proprietario"].strip()
    if "mercado" in dados and dados["mercado"] is not None:
        dados["mercado"] = dados["mercado"].strip()
    if "senha" in dados:
        if dados["senha"]:
            dados["senha"] = security.hash_senha(dados["senha"])
        else:
            dados.pop("senha")

    # O cliente nao pode alterar o campo "ativo" por meio deste schema.
    for campo, valor in dados.items():
        setattr(afiliado, campo, valor)

    db.commit()
    db.refresh(afiliado)
    return AfiliadoResponse.de(afiliado)


def deletar(db: Session, afiliado_id: int) -> None:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None:
        raise NaoEncontradoException("Afiliado nao encontrado.")

    # Exclusao logica: preserva produtos e historico para nao quebrar
    # listas de compras nem registros de preco.
    afiliado.ativo = False
    for produto in afiliado.produtos:
        produto.ativo = False
    db.commit()
