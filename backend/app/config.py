"""Runtime configuration. Every value can be overridden with an environment variable
(see .env.example at the repo root). Secrets are only ever read server-side."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Storage
    data_dir: Path = REPO_ROOT / "data"
    sample_data_dir: Path = REPO_ROOT / "sample_data"

    # Uploads
    max_upload_mb: float = 10.0
    allowed_extensions: tuple[str, ...] = (".pdf", ".md", ".markdown", ".txt")
    min_chars_per_pdf_page: int = 25  # below this average we treat a PDF as scanned

    # Chunking (characters)
    chunk_size: int = 900
    chunk_overlap: int = 150

    # Retrieval
    retrieval_candidates: int = 20  # per retriever, before fusion
    answer_max_passages: int = 8  # passages sent to the answer model
    rrf_k: int = 60
    plan_quota: int = 2  # min plan passages for change/comparison questions
    update_quota: int = 3  # min progress-update passages for change/status questions

    # Embeddings
    embedding_provider: Literal["local", "openai", "hash"] = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_dir: Path = REPO_ROOT / "models" / "all-MiniLM-L6-v2"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: SecretStr | None = None
    embedding_batch_size: int = 32

    # Answer generation
    llm_provider: Literal["none", "anthropic", "openai"] = "none"
    llm_model: str = "claude-sonnet-5"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None  # defaults per provider
    llm_max_tokens: int = 8192  # generous: "thinking" models count reasoning tokens against this
    # OpenAI-compatible servers only: none|low|medium|high. Defaults to "low" for Gemini so its
    # thinking step doesn't use up the output budget; leave unset for other servers.
    llm_reasoning_effort: str | None = None
    llm_timeout_s: float = 90.0
    llm_temperature: float = 0.0

    # Public demo: read-only sample project, no uploads/edits/deletes, rate-limited questions.
    # Use this for any internet-facing deployment; the app has no authentication.
    public_demo: bool = False
    ask_rate_per_client_per_min: int = 10
    ask_rate_global_per_min: int = 120

    # Security / logging
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_document_content: bool = False  # never log passage or question text unless explicitly enabled

    @property
    def llm_enabled(self) -> bool:
        return (
            self.llm_provider != "none" and self.llm_api_key is not None and bool(self.llm_api_key.get_secret_value())
        )

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "projectpulse.sqlite3"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
