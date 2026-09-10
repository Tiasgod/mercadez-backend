"""
Seguranca: hashing de senha (bcrypt) e emissao/validacao de JWT.

Equivalente Python de JwtService.java + BCryptPasswordEncoder do backend Java.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro. Nunca armazene a senha original."""
    return pwd_context.hash(senha)


def verificar_senha(senha_texto_puro: str, senha_hash: str) -> bool:
    """Compara uma senha em texto puro com o hash armazenado."""
    return pwd_context.verify(senha_texto_puro, senha_hash)


def gerar_token(id_: int, email: str, perfil: str) -> str:
    """
    Gera um token JWT.

    Claims: sub=email, id, perfil, iat, exp — mesmo formato do backend Java
    (JwtService.gerarToken), para manter compatibilidade com o frontend.
    """
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "id": id_,
        "perfil": perfil,
        "iat": agora,
        "exp": agora + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.secret_key_normalized, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    """Decodifica e valida um token JWT. Retorna None se invalido ou expirado."""
    try:
        return jwt.decode(token, settings.secret_key_normalized, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
