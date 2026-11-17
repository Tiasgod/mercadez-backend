"""Schemas de cadastro, autenticacao, atualizacao e resposta de usuarios."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.usuario import Perfil


class CadastroUsuarioRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(min_length=6, description="Senha deve ter no minimo 6 caracteres")
    cpf: Optional[str] = Field(default=None, max_length=14)


class AtualizarUsuarioRequest(BaseModel):
    """Campos opcionais permitem atualizar somente os dados enviados."""
    nome: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    senha: Optional[str] = Field(default=None, min_length=6)
    cpf: Optional[str] = Field(default=None, max_length=14)

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        for campo in ("nome", "email"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} nao pode ser nulo.")
        return self


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
