"""Application settings, loaded from environment variables / backend/.env."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # storage
    data_dir: Path = REPO_ROOT / "data"
    sqlite_path: Path | None = None
    upload_dir: Path | None = None
    chroma_dir: Path | None = None

    # limits
    max_upload_mb: int = Field(25, ge=1, le=200)
    max_files_per_request: int = Field(10, ge=1, le=50)

    # The embedder clamps this maximum to its tokenizer's sequence limit.
    chunk_target_tokens: int = Field(180, ge=50, le=2000)
    chunk_max_tokens: int = Field(250, ge=50, le=2000)
    chunk_overlap_tokens: int = Field(50, ge=0, le=1000)

    # embeddings. "hash" exists ONLY for automated tests / offline evaluation.
    embedding_backend: Literal["sentence-transformers", "hash"] = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # retrieval
    top_k: int = Field(5, ge=1, le=20)
    min_score: float = Field(0.25, ge=-1.0, le=1.0)

    # LLM
    llm_provider: Literal["groq"] = "groq"
    groq_api_key: SecretStr | None = None
    # llama-3.3-70b-versatile was retired by Groq on 2026-08-16. Check https://console.groq.com/docs/models for current names.
    groq_model: str = "openai/gpt-oss-120b"
    # Only sent for reasoning models (names containing "gpt-oss"). Lower effort = faster, cheaper answers.
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: int = Field(60, ge=5, le=300)

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @model_validator(mode="after")
    def _finish(self):
        self.data_dir = Path(self.data_dir).resolve()
        self.sqlite_path = Path(self.sqlite_path).resolve() if self.sqlite_path else self.data_dir / "app.db"
        self.upload_dir = Path(self.upload_dir).resolve() if self.upload_dir else self.data_dir / "uploads"
        self.chroma_dir = Path(self.chroma_dir).resolve() if self.chroma_dir else self.data_dir / "chroma"
        if self.chunk_max_tokens < self.chunk_target_tokens:
            raise ValueError("CHUNK_MAX_TOKENS must be at least CHUNK_TARGET_TOKENS")
        if self.chunk_overlap_tokens >= self.chunk_max_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_MAX_TOKENS")
        return self

    @property
    def llm_configured(self) -> bool:
        key = self.groq_api_key.get_secret_value().strip() if self.groq_api_key else ""
        return bool(key) and not key.lower().startswith("your_")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
