"""Equivalente a ContatoControllerTest.java"""


def test_enviar_contato_sucesso(client):
    resp = client.post(
        "/contato",
        json={"nome": "Ana", "email": "ana@email.com", "mensagem": "Gostaria de saber mais sobre o Mercadez."},
    )
    assert resp.status_code == 201


def test_enviar_contato_mensagem_curta(client):
    resp = client.post(
        "/contato",
        json={"nome": "Ana", "email": "ana@email.com", "mensagem": "oi"},
    )
    assert resp.status_code == 400
