"""
Equivalente Python de CadastroUsuarioRequest / LoginRequest / LoginResponse /
UsuarioResponse (dto/*.java para usuarios).

Os nomes de campo aqui reproduzem exatamente o JSON que o frontend ja envia
e espera receber, para nao exigir nenhuma mudanca no frontend.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.usuario import Perfil


class CadastroUsuarioRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(min_length=6, description="Senha deve ter no minimo 6 caracteres")
    cpf: Optional[str] = Field(default=None, max_length=14)


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    tipo: str = "Bearer"
    perfil: str
    id: int
    nome: str
    email: str


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    cpf: Optional[str] = None
    perfil: Perfil
    criadoEm: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, usuario) -> "UsuarioResponse":
        return cls(
            id=usuario.id,
            nome=usuario.nome,
            email=usuario.email,
            cpf=usuario.cpf,
            perfil=usuario.perfil,
            criadoEm=usuario.criado_em,
        )
