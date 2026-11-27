"""Equivalente Python de service/ProdutoService.java"""

from sqlalchemy import select, or_, and_, func, literal_column, text
import unicodedata
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


# Mesma expressão usada pelos índices PostgreSQL (migração 0006).
_ACENTOS = "áàâãäéèêëíìîïóòôõöúùûüçñýÿ"
_ASCII = "aaaaaeeeeiiiiooooouuuucnyy"


def normalizar_busca(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn").strip()


def _normalizado(db, coluna):
    if db.get_bind().dialect.name == "sqlite":
        db.connection().connection.driver_connection.create_function(
            "mercadez_normalizar", 1, lambda v: normalizar_busca(v or ""), deterministic=True)
        return func.mercadez_normalizar(coluna)
    return func.translate(func.lower(coluna), literal_column("'" + _ACENTOS + "'"),
                          literal_column("'" + _ASCII + "'"))


def _extrair_termos(texto: str) -> list[str]:
    return list(dict.fromkeys(normalizar_busca(texto).split()))


def _filtros_catalogo(db, consulta, mercado=None, categoria=None, preco_min=None, preco_max=None):
    if mercado:
        padrao = _criar_padrao(normalizar_busca(mercado))
        consulta = consulta.where(or_(
            Produto.loja_externa.has(_normalizado(db, LojaExterna.nome).like(padrao, escape="\\")),
            Produto.afiliado.has(_normalizado(db, Afiliado.mercado).like(padrao, escape="\\"))))
    if categoria:
        consulta = consulta.where(_normalizado(db, Produto.tags).like(
            _criar_padrao(normalizar_busca(categoria)), escape="\\"))
    if preco_min is not None:
        consulta = consulta.where(Produto.preco >= preco_min)
    if preco_max is not None:
        consulta = consulta.where(Produto.preco <= preco_max)
    return consulta


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


def buscar(db: Session, termo: str, limit: int = 100, offset: int = 0,
           com_imagem: bool = False, mercado=None, categoria=None,
           preco_min=None, preco_max=None, ordem="menor") -> list[ProdutoResponse]:
    nome = _normalizado(db, Produto.nome_produto)
    tags = _normalizado(db, Produto.tags)
    filtros = [or_(nome.like(_criar_padrao(t), escape="\\"),
                   tags.like(_criar_padrao(t), escape="\\"))
               for t in _extrair_termos(termo)]
    consulta = _consulta_base().where(*filtros)
    consulta = _filtros_catalogo(db, consulta, mercado, categoria, preco_min, preco_max)
    consulta = _filtrar_imagem(consulta, com_imagem)
    ordem_sql = Produto.preco.desc() if ordem == "maior" else Produto.preco.asc()
    if ordem == "nome":
        ordem_sql = nome.asc()
    consulta = consulta.order_by(ordem_sql, Produto.id.asc()).offset(offset).limit(limit)
    return [ProdutoResponse.de(p) for p in db.scalars(consulta).unique().all()]


def comparar(db: Session, nome: str, limit: int | None = None, offset: int = 0) -> list[ProdutoResponse]:
    # Rota legada de descoberta; a comparação exata usa o ID.
    if not nome.strip():
        raise NegocioException("Informe o nome do produto para comparar.")
    filtros = [_normalizado(db, Produto.nome_produto).like(_criar_padrao(t), escape="\\")
               for t in _extrair_termos(nome)]
    consulta = _consulta_base().where(*filtros).order_by(Produto.preco, Produto.id).offset(offset).limit(limit)
    return [ProdutoResponse.de(p) for p in db.scalars(consulta).unique().all()]


def comparar_por_id(db: Session, produto_id: int) -> list[ProdutoResponse]:
    referencia = buscar_por_id(db, produto_id)
    # Conservador: nome completo, incluindo marca, variante, peso e volume.
    # Não há EAN no modelo atual; não inferimos equivalência por similaridade.
    consulta = _consulta_base().where(
        func.trim(_normalizado(db, Produto.nome_produto)) == normalizar_busca(referencia.nomeProduto),
        Produto.preco > 0).order_by(Produto.preco, Produto.id)
    lojas = {}
    for p in db.scalars(consulta).unique().all():
        chave = (p.loja_externa_id, p.afiliado_id)
        lojas.setdefault(chave, ProdutoResponse.de(p))
    return list(lojas.values())


def sugestoes(db: Session, termo: str, limit: int = 10) -> list[str]:
    if len(termo.strip()) < 2:
        return []
    nome = _normalizado(db, Produto.nome_produto)
    filtros = [nome.like(_criar_padrao(t), escape="\\") for t in _extrair_termos(termo)]
    consulta = _consulta_base().with_only_columns(Produto.nome_produto).where(*filtros).distinct().order_by(Produto.nome_produto).limit(limit)
    exatas = list(db.scalars(consulta).all())
    # Sugestões aproximadas apenas quando pg_trgm estiver instalado.
    # Nunca misturamos variantes na comparação por ID.
    if exatas or db.get_bind().dialect.name != "postgresql":
        return exatas
    if not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")):
        return []
    termo_normalizado = normalizar_busca(termo)
    relevancia = func.word_similarity(termo_normalizado, nome)
    candidatos = (_consulta_base().with_only_columns(Produto.nome_produto, relevancia.label("relevancia"))
        .where(nome.op("%>")(termo_normalizado), relevancia >= 0.5)
        .distinct().order_by(relevancia.desc(), Produto.nome_produto).limit(limit))
    return [row[0] for row in db.execute(candidatos).all()]


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
