import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    # Banco de dados
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/mercadez"
    )

    # JWT
    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # CORS — lista de origens separadas por virgula
    CORS_ORIGINS: str = (
        "https://mercadez-ten.vercel.app,"
        "http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "http://localhost:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_secret_key(self):
        ambiente = os.getenv("ENVIRONMENT", "development").lower()

        if ambiente == "production":
            if self.SECRET_KEY == "troque-esta-chave-em-producao":
                raise ValueError(
                    "SECRET_KEY nao pode usar a chave padrao em producao."
                )

            if len(self.SECRET_KEY.strip()) < 32:
                raise ValueError(
                    "SECRET_KEY deve ter pelo menos 32 caracteres em producao."
                )

        return self

    @property
    def secret_key_normalized(self) -> str:
        return self.SECRET_KEY.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def database_url_normalized(self) -> str:
        """
        Normaliza URLs PostgreSQL fornecidas por plataformas
        como Railway, Render e Heroku.
        """

        url = self.DATABASE_URL.strip()

        if url.startswith("postgres://"):
            return url.replace(
                "postgres://",
                "postgresql+psycopg2://",
                1
            )

        if url.startswith("postgresql://"):
            return url.replace(
                "postgresql://",
                "postgresql+psycopg2://",
                1
            )

        return url


settings = Settings()
