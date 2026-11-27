from decimal import Decimal
from app.models import Produto, LojaExterna
from app.services import produto_service as service


def test_busca_acentos_e_comparacao(db_session):
    a = LojaExterna(nome='Nagumo Poá', dominio='nagumo.com.br')
    b = LojaExterna(nome='Nagumo Suzano', dominio='nagumo.com.br')
    db_session.add_all([a,b]); db_session.flush()
    produtos = [Produto(nome_produto=nome, preco=Decimal(preco), tags='Grãos', loja_externa_id=loja.id) for nome, preco, loja in [
        ('Feijão Kicaldo 1kg','8.50',a), ('Feijao Kicaldo 1kg','7.50',b),
        ('Feijão Kicaldo 5kg','30.00',b), ('Café Melitta 500g','20.00',a),
        ('Feijão Kicaldo 1kg','9.00',b)]]
    db_session.add_all(produtos); db_session.commit()
    for termo in ('feijao kicaldo','FEIJÃO KICALDO','kicaldo feijão'):
        assert len(service.buscar(db_session, termo)) == 4
    assert len(service.buscar(db_session,'cafe')) == 1
    assert len(service.buscar(db_session,'café')) == 1
    assert len(service.buscar(db_session,'feijão',mercado='poa',categoria='graos')) == 1
    assert service.buscar(db_session,'feijão',ordem='maior',limit=1)[0].preco == Decimal('30.00')
    assert service.buscar(db_session,'feijão',preco_max=8)[0].preco == Decimal('7.50')
    assert service.buscar(db_session,'feijão',limit=1,offset=1)[0].preco == Decimal('8.50')
    assert service.buscar_por_id(db_session,produtos[3].id).nomeProduto == 'Café Melitta 500g'
    comparacao = service.comparar_por_id(db_session,produtos[0].id)
    assert [p.preco for p in comparacao] == [Decimal('7.50'), Decimal('8.50')]
    assert 'Café Melitta 500g' in service.sugestoes(db_session,'cafe')
    assert service.buscar(db_session,'%') == []
