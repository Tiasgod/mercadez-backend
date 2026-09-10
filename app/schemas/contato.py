"""Equivalente Python de ContatoRequest."""
from pydantic import BaseModel, EmailStr, Field


class ContatoRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    mensagem: str = Field(min_length=10, max_length=2000)
