"""
Configuracao central da aplicacao.

Todos os valores sensiveis (chave secreta, URL do banco) vem de
variaveis de ambiente / arquivo .env — nunca ficam hardcoded no codigo.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Banco de dados
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/mercadez"

    # JWT
    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h, igual ao backend Java original

    # CORS — lista de origens separadas por virgula
    CORS_ORIGINS: str = (
        "https://mercadez-ten.vercel.app,"
        "http://localhost:5500,"
        "http://127.0.0.1:5500"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def secret_key_normalized(self) -> str:
        return self.SECRET_KEY.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url_normalized(self) -> str:
        """
        Plataformas como Railway/Render/Heroku fornecem DATABASE_URL no formato
        'postgres://...' ou 'postgresql://...', mas o SQLAlchemy com o driver
        psycopg2 precisa do prefixo 'postgresql+psycopg2://...'. Normaliza aqui
        em vez de exigir que a variavel de ambiente seja editada manualmente.
        """
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


settings = Settings()
