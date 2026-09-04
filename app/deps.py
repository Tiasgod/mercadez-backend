"""
Dependencias compartilhadas pelos routers: sessao de banco de dados
e extracao/validacao do usuario autenticado a partir do JWT.

IMPORTANTE (correcao de seguranca em relacao ao backend Java original):
no backend Java, a lista ROTAS_PROTEGIDAS existia em JwtAuthFilter mas
nunca era de fato usada para bloquear requisicoes — a unica protecao real
dependia do controller extrair `auth.getDetails()`, o que lancava
NullPointerException (HTTP 500) em vez de 401 quando nao havia token.
Aqui, as dependencias abaixo bloqueiam explicitamente o acesso e retornam
401/403 corretos.
"""
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import SessionLocal

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_claims_atuais(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Extrai e valida o token Bearer. Lanca 401 se ausente ou invalido."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacao nao informado.",
        )

    claims = security.decodificar_token(credentials.credentials)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado.",
        )
    return claims


def get_usuario_id_atual(claims: dict = Depends(get_claims_atuais)) -> int:
    """Garante que o token pertence a um usuario (CLIENTE/ADMIN), nao a um afiliado."""
    if claims.get("perfil") not in ("CLIENTE", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a usuarios.",
        )
    return int(claims["id"])


def get_afiliado_id_atual(claims: dict = Depends(get_claims_atuais)) -> int:
    """Garante que o token pertence a um afiliado (lojista)."""
    if claims.get("perfil") != "AFILIADO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a afiliados.",
        )
    return int(claims["id"])
