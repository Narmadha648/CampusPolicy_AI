"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://campuspolicy:campuspolicypass@localhost:5432/campuspolicy"
    sync_database_url: str = "postgresql://campuspolicy:campuspolicypass@localhost:5432/campuspolicy"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_in_production"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    session_expire_days: int = 7

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"
    groq_timeout_seconds: int = 60

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Chunking / retrieval ──────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_chunks_per_query: int = 6
    similarity_threshold: float = 0.35

    # ── File upload ───────────────────────────────────────────────────────────
    upload_dir: str = "../data/uploads"
    max_upload_mb: int = 50

    # ── FAISS ─────────────────────────────────────────────────────────────────
    faiss_index_dir: str = "../data/faiss_index"

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:5173,http://localhost:4173"

    # ── Rate limits ───────────────────────────────────────────────────────────
    auth_rate_limit: str = "20/minute"
    chat_rate_limit: str = "30/minute"

    # ── First admin credentials (used by create-admin CLI only) ───────────────
    admin_email: str = "admin@college.edu"
    admin_password: str = "ChangeMe123!"
    admin_name: str = "System Administrator"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
