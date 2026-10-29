"""Formato de resposta de erro — identico ao ErroResponse.java."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ErroResponse(BaseModel):
    status: int
    erro: str
    mensagem: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
