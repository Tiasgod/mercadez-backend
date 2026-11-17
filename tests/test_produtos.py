"""Equivalente a ProdutoControllerTest.java"""


def _criar_afiliado_e_logar(client, email="loja@email.com", cnpj="12345678000199"):
    client.post(
        "/afiliados",
        json={
            "nome_proprietario": "Joao Dono",
            "email": email,
            "senha": "senha123",
            "cnpj": cnpj,
            "mercado": "Mercado do Joao",
        },
    )
    login = client.post("/afiliados/login", json={"email": email, "senha": "senha123"})
    return login.json()["token"], login.json()["id"]


def test_produto_requer_autenticacao(client):
    resp = client.post("/produtos", json={"nomeProduto": "Arroz", "preco": "10.00", "quantidade": 5})
    assert resp.status_code == 401


def test_cadastro_e_listagem_produto(client):
    token, _ = _criar_afiliado_e_logar(client)

    resp = client.post(
        "/produtos",
        json={"nomeProduto": "Arroz 5kg", "tags": "graos", "preco": "24.90", "quantidade": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["mercado"] == "Mercado do Joao"

    listagem = client.get("/produtos")
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1


def test_buscar_e_comparar(client):
    token, _ = _criar_afiliado_e_logar(client)
    client.post(
        "/produtos",
        json={"nomeProduto": "Feijao Carioca", "tags": "graos", "preco": "8.50", "quantidade": 20},
        headers={"Authorization": f"Bearer {token}"},
    )

    busca = client.get("/produtos/buscar", params={"q": "feijao"})
    assert busca.status_code == 200
    assert len(busca.json()) == 1

    comparar = client.get("/produtos/comparar", params={"nome": "feijao"})
    assert comparar.status_code == 200


def test_atualizar_produto_de_outro_afiliado_e_negado(client):
    token1, _ = _criar_afiliado_e_logar(client, email="loja1@email.com", cnpj="11111111000101")
    token2, _ = _criar_afiliado_e_logar(client, email="loja2@email.com", cnpj="22222222000102")

    criado = client.post(
        "/produtos",
        json={"nomeProduto": "Leite", "preco": "5.00", "quantidade": 3},
        headers={"Authorization": f"Bearer {token1}"},
    )
    produto_id = criado.json()["id"]

    resp = client.put(
        f"/produtos/{produto_id}",
        json={"nomeProduto": "Leite Editado", "preco": "6.00", "quantidade": 3},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403


def test_deletar_produto_e_soft_delete(client):
    token, _ = _criar_afiliado_e_logar(client)
    criado = client.post(
        "/produtos",
        json={"nomeProduto": "Macarrao", "preco": "4.50", "quantidade": 15},
        headers={"Authorization": f"Bearer {token}"},
    )
    produto_id = criado.json()["id"]

    resp = client.delete(f"/produtos/{produto_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    listagem = client.get("/produtos")
    assert len(listagem.json()) == 0



def test_comparacao_considera_produtos_de_mercados_diferentes(client):
    token1, _ = _criar_afiliado_e_logar(
        client, email="comparacao1@email.com", cnpj="33333333000101"
    )
    token2, _ = _criar_afiliado_e_logar(
        client, email="comparacao2@email.com", cnpj="44444444000102"
    )
    client.post(
        "/produtos",
        json={"nomeProduto": "Arroz Camil 5kg", "preco": "25.90", "quantidade": 10},
        headers={"Authorization": f"Bearer {token1}"},
    )
    client.post(
        "/produtos",
        json={"nomeProduto": "Arroz Camil 5kg", "preco": "22.90", "quantidade": 8},
        headers={"Authorization": f"Bearer {token2}"},
    )

    resp = client.get("/comparacao", params={"produto": "Arroz Camil"})
    assert resp.status_code == 200
    resultado = resp.json()[0]
    assert len(resultado["precos"]) == 2
    assert resultado["menor_preco"] == "22.90"
    assert resultado["economia"] == "3.00"


def test_ofertas_inclui_comparacao_de_mercados_afiliados(client):
    token1, _ = _criar_afiliado_e_logar(
        client, email="oferta1@email.com", cnpj="55555555000101"
    )
    token2, _ = _criar_afiliado_e_logar(
        client, email="oferta2@email.com", cnpj="66666666000102"
    )
    for token, preco in ((token1, "12.00"), (token2, "9.00")):
        client.post(
            "/produtos",
            json={"nomeProduto": "Feijao Kicaldo 1kg", "preco": preco, "quantidade": 10},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = client.get("/ofertas")
    assert resp.status_code == 200
    assert any(item["produto"] == "Feijao Kicaldo 1kg" for item in resp.json())
