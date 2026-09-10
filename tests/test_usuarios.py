"""Equivalente a UsuarioControllerTest.java"""


def test_cadastro_usuario_sucesso(client):
    resp = client.post(
        "/usuarios/cadastro",
        json={"nome": "Carlos Silva", "email": "carlos@email.com", "senha": "senha123", "cpf": "11122233344"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "carlos@email.com"
    assert "senha" not in body


def test_cadastro_usuario_email_duplicado(client):
    payload = {"nome": "Carlos Silva", "email": "dup@email.com", "senha": "senha123"}
    client.post("/usuarios/cadastro", json=payload)
    resp = client.post("/usuarios/cadastro", json=payload)
    assert resp.status_code == 400
    assert resp.json()["erro"] == "Erro de negocio"


def test_cadastro_usuario_senha_curta(client):
    resp = client.post(
        "/usuarios/cadastro",
        json={"nome": "Carlos Silva", "email": "carlos2@email.com", "senha": "123"},
    )
    assert resp.status_code == 400


def test_login_sucesso(client):
    client.post(
        "/usuarios/cadastro",
        json={"nome": "Maria", "email": "maria@email.com", "senha": "senha123"},
    )
    resp = client.post("/usuarios/login", json={"email": "maria@email.com", "senha": "senha123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["perfil"] == "CLIENTE"
    assert body["token"]


def test_login_senha_incorreta(client):
    client.post(
        "/usuarios/cadastro",
        json={"nome": "Maria", "email": "maria2@email.com", "senha": "senha123"},
    )
    resp = client.post("/usuarios/login", json={"email": "maria2@email.com", "senha": "errada"})
    assert resp.status_code == 401


def test_me_sem_token(client):
    resp = client.get("/usuarios/me")
    assert resp.status_code == 401


def test_me_com_token(client):
    client.post(
        "/usuarios/cadastro",
        json={"nome": "Joao", "email": "joao@email.com", "senha": "senha123"},
    )
    login = client.post("/usuarios/login", json={"email": "joao@email.com", "senha": "senha123"})
    token = login.json()["token"]

    resp = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "joao@email.com"
