from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação validadas com Pydantic Settings."""

    APP_NAME: str = "Jet Food Studio IA"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Microsserviço de Visão Computacional e IA para padronização, diagnóstico "
        "e tratamento gastronômico de fotos de cardápio para plataformas de delivery (iFood)."
    )
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Limites e Segurança
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    ]
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Motor de IA e Concorrência
    AI_MODEL_NAME: str = "u2netp"
    PRELOAD_AI_MODEL: bool = True
    MAX_WORKER_THREADS: int = 4

    # Padrões de Saída
    DEFAULT_OUTPUT_FORMAT: str = "WEBP"
    DEFAULT_OUTPUT_QUALITY: int = 92

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Singleton em cache das configurações do sistema."""
    return Settings()
