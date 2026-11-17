"""Schemas de cadastro, atualizacao e resposta de afiliados/lojistas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class CadastroAfiliadoRequest(BaseModel):
    nome_proprietario: str = Field(min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(min_length=6, description="Senha deve ter no minimo 6 caracteres")
    cnpj: str = Field(min_length=14, max_length=18)
    endereco: Optional[str] = Field(default=None, max_length=200)
    telefone: Optional[str] = Field(default=None, max_length=20)
    mercado: str = Field(min_length=1, max_length=150)
    categoria: Optional[str] = Field(default=None, max_length=100)
    funcionarios: Optional[int] = Field(default=None, ge=0)
    pagamento: Optional[str] = Field(default=None, max_length=200)


class AtualizarAfiliadoRequest(BaseModel):
    """Campos opcionais para permitir atualizacao sem reenviar a senha."""
    nome_proprietario: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    senha: Optional[str] = Field(default=None, min_length=6)
    cnpj: Optional[str] = Field(default=None, min_length=14, max_length=18)
    endereco: Optional[str] = Field(default=None, max_length=200)
    telefone: Optional[str] = Field(default=None, max_length=20)
    mercado: Optional[str] = Field(default=None, min_length=1, max_length=150)
    categoria: Optional[str] = Field(default=None, max_length=100)
    funcionarios: Optional[int] = Field(default=None, ge=0)
    pagamento: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        for campo in ("nome_proprietario", "email", "cnpj", "mercado"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} nao pode ser nulo.")
        return self


class AfiliadoResponse(BaseModel):
    id: int
    nome_proprietario: str
    email: str
    cnpj: str
    endereco: Optional[str] = None
    telefone: Optional[str] = None
    mercado: str
    categoria: Optional[str] = None
    funcionarios: Optional[int] = None
    pagamento: Optional[str] = None
    ativo: bool
    criadoEm: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def de(cls, afiliado) -> "AfiliadoResponse":
        return cls(
            id=afiliado.id,
            nome_proprietario=afiliado.nome_proprietario,
            email=afiliado.email,
            cnpj=afiliado.cnpj,
            endereco=afiliado.endereco,
            telefone=afiliado.telefone,
            mercado=afiliado.mercado,
            categoria=afiliado.categoria,
            funcionarios=afiliado.funcionarios,
            pagamento=afiliado.pagamento,
            ativo=afiliado.ativo,
            criadoEm=afiliado.criado_em,
        )
