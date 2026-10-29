from decimal import Decimal

from pydantic import BaseModel


class ResumoGeralResponse(BaseModel):
    totalUsuarios: int
    totalAfiliadosAtivos: int
    totalProdutosAtivos: int
    precoMedioProdutos: Decimal


class ProdutoMaisListadoResponse(BaseModel):
    produtoId: int
    nome: str
    vezesAdicionadoEmListas: int


class AfiliadoTopResponse(BaseModel):
    afiliadoId: int
    mercado: str
    totalProdutosAtivos: int


class CrescimentoMensalResponse(BaseModel):
    mes: str
    novosUsuarios: int
    novosAfiliados: int


class DashboardResponse(BaseModel):
    resumo: ResumoGeralResponse
    produtosMaisListados: list[ProdutoMaisListadoResponse]
    afiliadosComMaisProdutos: list[AfiliadoTopResponse]
    crescimentoMensal: list[CrescimentoMensalResponse]