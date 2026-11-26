"""Equivalente Python de service/ProdutoService.java"""

from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session, joinedload

from app.exceptions import (
    AcessoNegadoException,
    NaoEncontradoException,
    NegocioException,
)
from app.models.afiliado import Afiliado
from app.models.historico_preco import HistoricoPreco
from app.models.loja_externa import LojaExterna
from app.models.produto import Produto
from app.schemas.produto import CadastroProdutoRequest, ProdutoResponse


def _registrar_preco(
    db: Session,
    produto_id: int,
    preco,
) -> None:
    """Grava um snapshot do preco no historico."""

    db.add(
        HistoricoPreco(
            produto_id=produto_id,
            preco=preco,
        )
    )


def _consulta_base():
    """Consulta base dos produtos ativos."""

    return (
        select(Produto)
        .options(
            joinedload(Produto.afiliado),
            joinedload(Produto.loja_externa),
        )
        .where(
            Produto.ativo.is_(True),
            or_(
                Produto.afiliado.has(
                    Afiliado.ativo.is_(True)
                ),
                Produto.loja_externa.has(
                    LojaExterna.ativo.is_(True)
                ),
            ),
        )
    )


def _filtrar_imagem(consulta, com_imagem: bool):
    """Filtra produtos que possuem imagem principal."""

    if com_imagem:
        consulta = consulta.where(
            Produto.imagem_url.is_not(None),
            func.trim(Produto.imagem_url) != "",
        )

    return consulta


def _extrair_termos(texto: str) -> list[str]:
    """Separa as palavras digitadas na pesquisa."""

    return list(dict.fromkeys(texto.strip().lower().split()))


def _criar_padrao(termo: str) -> str:
    """Cria um padrao de pesquisa com caracteres especiais escapados."""

    termo = (
        termo.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    return f"%{termo}%"


def cadastrar(
    db: Session,
    req: CadastroProdutoRequest,
    afiliado_id: int,
) -> ProdutoResponse:

    afiliado = db.get(Afiliado, afiliado_id)

    if afiliado is None or not afiliado.ativo:
        raise NaoEncontradoException(
            "Afiliado nao encontrado ou desativado."
        )

    produto = Produto(
        nome_produto=req.nomeProduto,
        tags=req.tags,
        imagem_url=req.imagemUrl or (
            req.imagensUrls[0] if req.imagensUrls else None
        ),
        imagens_urls=req.imagensUrls or (
            [req.imagemUrl] if req.imagemUrl else []
        ),
        preco=req.preco,
        quantidade=req.quantidade,
        afiliado_id=afiliado_id,
    )

    db.add(produto)
    db.flush()

    _registrar_preco(
        db,
        produto.id,
        produto.preco,
    )

    db.commit()
    db.refresh(produto)

    return ProdutoResponse.de(produto)


def listar_todos(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    com_imagem: bool = False,
) -> list[ProdutoResponse]:
    """Lista produtos ativos com paginacao."""

    consulta = _consulta_base()

    consulta = _filtrar_imagem(
        consulta,
        com_imagem,
    )

    consulta = (
        consulta
        .order_by(Produto.id.asc())
        .offset(offset)
        .limit(limit)
    )

    produtos = db.scalars(
        consulta
    ).unique().all()

    return [
        ProdutoResponse.de(p)
        for p in produtos
    ]


def listar_por_afiliado(
    db: Session,
    afiliado_id: int,
    limit: int = 100,
    offset: int = 0,
    com_imagem: bool = False,
) -> list[ProdutoResponse]:
    """Lista produtos de um afiliado com paginacao."""

    consulta = (
        select(Produto)
        .options(
            joinedload(Produto.afiliado),
            joinedload(Produto.loja_externa),
        )
        .where(
            Produto.afiliado_id == afiliado_id,
            Produto.ativo.is_(True),
        )
    )

    consulta = _filtrar_imagem(
        consulta,
        com_imagem,
    )

    consulta = (
        consulta
        .order_by(Produto.id.asc())
        .offset(offset)
        .limit(limit)
    )

    produtos = db.scalars(
        consulta
    ).unique().all()

    return [
        ProdutoResponse.de(p)
        for p in produtos
    ]


def buscar(
    db: Session,
    termo: str,
    limit: int = 100,
    offset: int = 0,
    com_imagem: bool = False,
) -> list[ProdutoResponse]:
    """
    Busca produtos por nome ou tag.

    Aceita multiplas palavras independentemente da ordem.

    Exemplo:
        arroz camil
        camil arroz
        arroz camil 5kg
    """

    if not termo or not termo.strip():
        return listar_todos(
            db,
            limit=limit,
            offset=offset,
            com_imagem=com_imagem,
        )

    termos = _extrair_termos(termo)

    filtros = []

    for palavra in termos:

        padrao = _criar_padrao(palavra)

        filtros.append(
            or_(
                Produto.nome_produto.ilike(
                    padrao,
                    escape="\\",
                ),
                Produto.tags.ilike(
                    padrao,
                    escape="\\",
                ),
            )
        )

    consulta = _consulta_base().where(
        and_(*filtros)
    )

    consulta = _filtrar_imagem(
        consulta,
        com_imagem,
    )

    consulta = (
        consulta
        .order_by(
            Produto.preco.asc(),
            Produto.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )

    produtos = db.scalars(
        consulta
    ).unique().all()

    return [
        ProdutoResponse.de(p)
        for p in produtos
    ]


def comparar(
    db: Session,
    nome: str,
) -> list[ProdutoResponse]:
    """
    Compara precos de produtos em diferentes supermercados.

    Aceita multiplas palavras independentemente da ordem.
    Ordena os resultados do menor para o maior preco.
    """

    if not nome or not nome.strip():
        raise NegocioException(
            "Informe o nome do produto para comparar."
        )

    termos = _extrair_termos(nome)

    filtros = [
        Produto.nome_produto.ilike(
            _criar_padrao(palavra),
            escape="\\",
        )
        for palavra in termos
    ]

    consulta = (
        _consulta_base()
        .where(
            and_(*filtros)
        )
        .order_by(
            Produto.preco.asc(),
            Produto.id.asc(),
        )
    )

    produtos = db.scalars(
        consulta
    ).unique().all()

    return [
        ProdutoResponse.de(p)
        for p in produtos
    ]


def atualizar(
    db: Session,
    produto_id: int,
    req: CadastroProdutoRequest,
    afiliado_id: int,
) -> ProdutoResponse:

    produto = db.get(Produto, produto_id)

    if produto is None:
        raise NaoEncontradoException(
            "Produto nao encontrado."
        )

    if produto.afiliado_id != afiliado_id:
        raise AcessoNegadoException(
            "Voce nao tem permissao para editar este produto."
        )

    preco_mudou = produto.preco != req.preco

    produto.nome_produto = req.nomeProduto
    produto.tags = req.tags

    # Preserva imagens em atualizacoes antigas do front.
    if (
        "imagemUrl" in req.model_fields_set
        or "imagensUrls" in req.model_fields_set
    ):
        produto.imagem_url = req.imagemUrl or (
            req.imagensUrls[0] if req.imagensUrls else None
        )

        produto.imagens_urls = req.imagensUrls or (
            [req.imagemUrl] if req.imagemUrl else []
        )

    produto.preco = req.preco
    produto.quantidade = req.quantidade

    if preco_mudou:
        _registrar_preco(
            db,
            produto.id,
            req.preco,
        )

    db.commit()
    db.refresh(produto)

    return ProdutoResponse.de(produto)

def buscar_por_id(
    db: Session,
    produto_id: int,
) -> ProdutoResponse:

    consulta = _consulta_base().where(
        Produto.id == produto_id
    )

    produto = db.scalars(
        consulta
    ).unique().first()

    if produto is None:
        raise NaoEncontradoException(
            "Produto nao encontrado."
        )

    return ProdutoResponse.de(produto)

def deletar(
    db: Session,
    produto_id: int,
    afiliado_id: int,
) -> None:

    produto = db.get(Produto, produto_id)

    if produto is None:
        raise NaoEncontradoException(
            "Produto nao encontrado."
        )

    if produto.afiliado_id != afiliado_id:
        raise AcessoNegadoException(
            "Voce nao tem permissao para excluir este produto."
        )

    produto.ativo = False

    db.commit()
