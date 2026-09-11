"""Testes do novo recurso /listas (nao existia no backend Java)."""


def _criar_usuario_e_logar(client, email="cliente@email.com"):
    client.post("/usuarios/cadastro", json={"nome": "Cliente", "email": email, "senha": "senha123"})
    login = client.post("/usuarios/login", json={"email": email, "senha": "senha123"})
    return login.json()["token"]


def _criar_produto(client):
    client.post(
        "/afiliados",
        json={
            "nome_proprietario": "Joao Dono",
            "email": "loja@email.com",
            "senha": "senha123",
            "cnpj": "12345678000199",
            "mercado": "Mercado do Joao",
        },
    )
    login = client.post("/afiliados/login", json={"email": "loja@email.com", "senha": "senha123"})
    token = login.json()["token"]
    produto = client.post(
        "/produtos",
        json={"nomeProduto": "Arroz 5kg", "preco": "24.90", "quantidade": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    return produto.json()["id"]


def test_listas_requer_autenticacao(client):
    resp = client.get("/listas")
    assert resp.status_code == 401


def test_adicionar_listar_remover_item(client):
    produto_id = _criar_produto(client)
    token = _criar_usuario_e_logar(client)
    headers = {"Authorization": f"Bearer {token}"}

    add = client.post("/listas", json={"produtoId": produto_id, "quantidade": 2}, headers=headers)
    assert add.status_code == 201
    assert add.json()["nome"] == "Arroz 5kg"
    assert add.json()["quantidade"] == 2

    listagem = client.get("/listas", headers=headers)
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1

    item_id = add.json()["id"]
    remocao = client.delete(f"/listas/{item_id}", headers=headers)
    assert remocao.status_code == 204

    listagem2 = client.get("/listas", headers=headers)
    assert len(listagem2.json()) == 0


def test_economia_compara_com_produto_mais_barato(client):
    """Mesmo produto (nome igual) em 2 afiliados com precos diferentes:
    a lista deve apontar o mais barato e calcular a economia correta."""
    # Afiliado 1: Arroz 5kg a 24.90
    produto_caro_id = _criar_produto(client)

    # Afiliado 2: mesmo produto, mais barato
    client.post(
        "/afiliados",
        json={
            "nome_proprietario": "Maria Dona",
            "email": "loja3@email.com",
            "senha": "senha123",
            "cnpj": "11122233000144",
            "mercado": "Mercado da Maria",
        },
    )
    login2 = client.post("/afiliados/login", json={"email": "loja3@email.com", "senha": "senha123"})
    token2 = login2.json()["token"]
    client.post(
        "/produtos",
        json={"nomeProduto": "Arroz 5kg", "preco": "19.90", "quantidade": 5},
        headers={"Authorization": f"Bearer {token2}"},
    )

    token_usuario = _criar_usuario_e_logar(client)
    headers = {"Authorization": f"Bearer {token_usuario}"}

    client.post("/listas", json={"produtoId": produto_caro_id, "quantidade": 2}, headers=headers)

    resp = client.get("/listas/economia", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["totalAtual"] == "49.80"       # 24.90 * 2
    assert body["totalOtimizado"] == "39.80"   # 19.90 * 2
    assert body["economiaTotal"] == "10.00"
    assert body["itens"][0]["mercadoMaisBarato"] == "Mercado da Maria"


def test_afiliado_nao_acessa_lista_de_usuario(client):
    """Token de AFILIADO nao pode ser usado em /listas (rota exclusiva de usuario)."""
    client.post(
        "/afiliados",
        json={
            "nome_proprietario": "Joao",
            "email": "loja2@email.com",
            "senha": "senha123",
            "cnpj": "99999999000188",
            "mercado": "Loja X",
        },
    )
    login = client.post("/afiliados/login", json={"email": "loja2@email.com", "senha": "senha123"})
    token = login.json()["token"]

    resp = client.get("/listas", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403