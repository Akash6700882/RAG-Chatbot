"""Centralized application settings loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM provider
    llm_provider: Literal["anthropic", "gemini", "groq"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Vector store
    vector_db: Literal["chroma", "faiss"] = "chroma"
    vector_db_path: str = "./data/vectorstore"

    # Ingestion
    upload_dir: str = "./data/uploads"
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Auth / JWT
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # App
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "*"

    # RAG tuning
    retrieval_top_k: int = 4
    max_generation_retries: int = 2
    conversation_history_turns: int = 6

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the .env file is only parsed once per process."""
    return Settings()
