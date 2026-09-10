"""
Equivalente Python dos DTOs de Afiliado.

O backend Java original usa snake_case para o campo nome_proprietario,
comentado explicitamente como "para bater com o payload do frontend" —
preservado aqui do mesmo jeito.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


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
