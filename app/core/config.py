"""Configuration centralisée chargée depuis les variables d'environnement."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paramètres de l'application lus depuis .env via pydantic-settings."""

    openrouter_api_key: str
    brave_api_key: str | None = None  # optionnel — active Brave Search dans le Researcher

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

    @property
    def database_url_psycopg(self) -> str:
        """URL PostgreSQL au format psycopg3 (sans +asyncpg) pour le checkpointer LangGraph."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
