"""Equivalente a AfiliadoControllerTest.java"""


def _payload_afiliado(email="loja@email.com", cnpj="12345678000199"):
    return {
        "nome_proprietario": "Joao Dono",
        "email": email,
        "senha": "senha123",
        "cnpj": cnpj,
        "endereco": "Rua A, 100",
        "telefone": "11999999999",
        "mercado": "Mercado do Joao",
        "categoria": "Bairro",
        "funcionarios": 5,
        "pagamento": "cartao, dinheiro",
    }


def test_cadastro_afiliado_sucesso(client):
    resp = client.post("/afiliados", json=_payload_afiliado())
    assert resp.status_code == 201
    body = resp.json()
    assert body["nome_proprietario"] == "Joao Dono"
    assert body["ativo"] is True


def test_cadastro_afiliado_cnpj_duplicado(client):
    client.post("/afiliados", json=_payload_afiliado(email="a@email.com", cnpj="11111111000191"))
    resp = client.post("/afiliados", json=_payload_afiliado(email="b@email.com", cnpj="11111111000191"))
    assert resp.status_code == 400


def test_login_e_me_afiliado(client):
    client.post("/afiliados", json=_payload_afiliado())
    login = client.post("/afiliados/login", json={"email": "loja@email.com", "senha": "senha123"})
    assert login.status_code == 200
    assert login.json()["perfil"] == "AFILIADO"

    token = login.json()["token"]
    resp = client.get("/afiliados/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "loja@email.com"


def test_usuario_nao_acessa_rota_de_afiliado(client):
    """Token de USUARIO nao pode ser usado em rota exclusiva de AFILIADO."""
    client.post("/usuarios/cadastro", json={"nome": "Xavier", "email": "x@email.com", "senha": "senha123"})
    login = client.post("/usuarios/login", json={"email": "x@email.com", "senha": "senha123"})
    token = login.json()["token"]

    resp = client.get("/afiliados/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
