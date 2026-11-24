from decimal import Decimal

from app.models.loja_externa import LojaExterna
from app.models.produto import Produto
from app.scripts.scraper_nagumo import _extrair_imagens, _salvar_produto
from app.schemas.produto import ProdutoResponse


def test_extracao_variantes_duplicados_e_urls_relativas():
    produto = {"productName": "Cafe", "price": {"sales": {"value": 12}},
               "images": [{"url": "/img/a.jpg"}, {"src": "https://img.exemplo.com/b.jpg"},
                          {"url": "/img/a.jpg"}],
               "imageGroups": [{"images": [{"link": "https://img.exemplo.com/c.jpg"}]}]}
    assert _extrair_imagens(produto) == ["https://www.nagumo.com.br/img/a.jpg",
                                            "https://img.exemplo.com/b.jpg",
                                            "https://img.exemplo.com/c.jpg"]


def test_scraper_salva_fotos_e_preserva_historico(db_session):
    loja = LojaExterna(nome="Nagumo Teste", dominio="www.nagumo.com.br", plataforma="SFCC")
    db_session.add(loja)
    db_session.flush()
    prod = {"productName": "Cafe", "price": {"sales": {"value": "12.00"}},
            "images": ["https://img.exemplo.com/a.jpg", "https://img.exemplo.com/b.jpg"]}
    existentes, historicos = {}, set()
    assert _salvar_produto(db_session, loja, prod, existentes, historicos) == "novo"
    db_session.commit()
    produto = db_session.query(Produto).filter_by(nome_produto="Cafe").one()
    assert ProdutoResponse.de(produto).imagensUrls == prod["images"]
    assert ProdutoResponse.de(produto).imagemUrl == prod["images"][0]
    prod["images"] = ["https://img.exemplo.com/c.jpg"]
    assert _salvar_produto(db_session, loja, prod, existentes, historicos) == "sem_alteracao"
    db_session.commit()
    assert len(produto.imagens_urls) == 3
    assert produto.preco == Decimal("12.00")
