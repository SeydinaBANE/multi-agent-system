"""Configuration centralisée chargée depuis les variables d'environnement."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paramètres de l'application lus depuis .env via pydantic-settings."""

    openrouter_api_key: str

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/multiagent"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    model_fast: str = "anthropic/claude-haiku-4-5"
    model_default: str = "anthropic/claude-haiku-4-5"
    model_smart: str = "anthropic/claude-haiku-4-5"

    # Origines CORS autorisées — surcharger via ALLOWED_ORIGINS en prod
    allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env"}


settings = Settings()
