"""Equivalente Python de service/ContatoService.java"""
from sqlalchemy.orm import Session

from app.models.contato import Contato
from app.schemas.contato import ContatoRequest


def enviar(db: Session, req: ContatoRequest) -> None:
    contato = Contato(
        nome=req.nome,
        email=req.email.lower(),
        mensagem=req.mensagem,
    )
    db.add(contato)
    db.commit()
