"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Mem0 memory service
    mem0_api_key: str = ""

    # Workspace
    workspace_root: Path = Path("./workspace")

    # Data paths
    chroma_persist_dir: Path = Path("./data/chroma")
    sqlite_db_path: Path = Path("./data/conversations.db")
    checkpoint_db_path: Path = Path("./data/checkpoints.db")

    # Logging
    log_level: str = "INFO"

    # LLM parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Graph execution
    graph_recursion_limit: int = 60


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    settings = Settings()  # type: ignore[call-arg]

    # Ensure data directories exist
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    settings.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)

    return settings
