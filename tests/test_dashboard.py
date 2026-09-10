"""Testes do novo recurso /dashboard (restrito a perfil ADMIN)."""
from app.models.usuario import Perfil, Usuario


def _criar_admin_e_logar(client, db_session, email="admin@email.com"):
    client.post("/usuarios/cadastro", json={"nome": "Admin", "email": email, "senha": "senha123"})
    usuario = db_session.query(Usuario).filter_by(email=email).one()
    usuario.perfil = Perfil.ADMIN
    db_session.commit()
    login = client.post("/usuarios/login", json={"email": email, "senha": "senha123"})
    return login.json()["token"]


def _criar_cliente_e_logar(client, email="cliente@email.com"):
    client.post("/usuarios/cadastro", json={"nome": "Cliente", "email": email, "senha": "senha123"})
    login = client.post("/usuarios/login", json={"email": email, "senha": "senha123"})
    return login.json()["token"]


def test_dashboard_requer_autenticacao(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 401


def test_cliente_comum_nao_acessa_dashboard(client):
    token = _criar_cliente_e_logar(client)
    resp = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_acessa_dashboard_com_metricas(client, db_session):
    client.post(
        "/afiliados",
        json={
            "nome_proprietario": "Joao",
            "email": "loja@email.com",
            "senha": "senha123",
            "cnpj": "12345678000199",
            "mercado": "Mercado do Joao",
        },
    )
    login = client.post("/afiliados/login", json={"email": "loja@email.com", "senha": "senha123"})
    token_afiliado = login.json()["token"]
    client.post(
        "/produtos",
        json={"nomeProduto": "Arroz 5kg", "preco": "24.90", "quantidade": 10},
        headers={"Authorization": f"Bearer {token_afiliado}"},
    )

    token_admin = _criar_admin_e_logar(client, db_session)
    resp = client.get("/dashboard", headers={"Authorization": f"Bearer {token_admin}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["resumo"]["totalAfiliadosAtivos"] == 1
    assert body["resumo"]["totalProdutosAtivos"] == 1
    assert body["resumo"]["precoMedioProdutos"] == "24.90"
    assert len(body["crescimentoMensal"]) >= 1