"""
Regras do dashboard administrativo — apenas leitura/agregacao, sem
efeitos colaterais. Todas as queries usam GROUP BY / func do proprio
Postgres em vez de trazer os dados pra memoria e agregar em Python,
pra escalar melhor conforme a base cresce.
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.afiliado import Afiliado
from app.models.lista import ListaItem
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.schemas.dashboard import (
    AfiliadoTopResponse,
    CrescimentoMensalResponse,
    DashboardResponse,
    ProdutoMaisListadoResponse,
    ResumoGeralResponse,
)


def _resumo_geral(db: Session) -> ResumoGeralResponse:
    total_usuarios = db.scalar(select(func.count(Usuario.id))) or 0
    total_afiliados = db.scalar(
        select(func.count(Afiliado.id)).where(Afiliado.ativo.is_(True))
    ) or 0
    total_produtos = db.scalar(
        select(func.count(Produto.id)).where(Produto.ativo.is_(True))
    ) or 0
    preco_medio = db.scalar(
        select(func.avg(Produto.preco)).where(Produto.ativo.is_(True))
    ) or Decimal("0")

    return ResumoGeralResponse(
        totalUsuarios=total_usuarios,
        totalAfiliadosAtivos=total_afiliados,
        totalProdutosAtivos=total_produtos,
        precoMedioProdutos=Decimal(preco_medio).quantize(Decimal("0.01")),
    )


def _produtos_mais_listados(db: Session, limite: int = 10) -> list[ProdutoMaisListadoResponse]:
    linhas = db.execute(
        select(
            Produto.id,
            Produto.nome_produto,
            func.count(ListaItem.id).label("vezes"),
        )
        .join(ListaItem, ListaItem.produto_id == Produto.id)
        .group_by(Produto.id, Produto.nome_produto)
        .order_by(func.count(ListaItem.id).desc())
        .limit(limite)
    ).all()

    return [
        ProdutoMaisListadoResponse(produtoId=r.id, nome=r.nome_produto, vezesAdicionadoEmListas=r.vezes)
        for r in linhas
    ]


def _afiliados_com_mais_produtos(db: Session, limite: int = 10) -> list[AfiliadoTopResponse]:
    linhas = db.execute(
        select(
            Afiliado.id,
            Afiliado.mercado,
            func.count(Produto.id).label("total"),
        )
        .join(Produto, Produto.afiliado_id == Afiliado.id)
        .where(Produto.ativo.is_(True))
        .group_by(Afiliado.id, Afiliado.mercado)
        .order_by(func.count(Produto.id).desc())
        .limit(limite)
    ).all()

    return [
        AfiliadoTopResponse(afiliadoId=r.id, mercado=r.mercado, totalProdutosAtivos=r.total)
        for r in linhas
    ]


def _contagem_por_mes(datas: list) -> dict[str, int]:
    """Agrupa uma lista de datetimes em contagem por 'YYYY-MM'. Feito em
    Python (em vez de date_trunc do Postgres) para funcionar igual em
    qualquer banco, inclusive o SQLite usado nos testes."""
    contagem: dict[str, int] = {}
    for data in datas:
        chave = data.strftime("%Y-%m")
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def _crescimento_mensal(db: Session, meses: int = 6) -> list[CrescimentoMensalResponse]:
    datas_usuarios = db.scalars(select(Usuario.criado_em)).all()
    datas_afiliados = db.scalars(select(Afiliado.criado_em)).all()

    usuarios_por_mes = _contagem_por_mes(datas_usuarios)
    afiliados_por_mes = _contagem_por_mes(datas_afiliados)

    meses_ordenados = sorted(set(usuarios_por_mes) | set(afiliados_por_mes))[-meses:]

    return [
        CrescimentoMensalResponse(
            mes=mes,
            novosUsuarios=usuarios_por_mes.get(mes, 0),
            novosAfiliados=afiliados_por_mes.get(mes, 0),
        )
        for mes in meses_ordenados
    ]


def montar_dashboard(db: Session) -> DashboardResponse:
    return DashboardResponse(
        resumo=_resumo_geral(db),
        produtosMaisListados=_produtos_mais_listados(db),
        afiliadosComMaisProdutos=_afiliados_com_mais_produtos(db),
        crescimentoMensal=_crescimento_mensal(db),
    )