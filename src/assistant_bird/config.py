"""Application configuration loaded from environment variables.

All data paths default to the platform-appropriate user data directory
(via get_app_dir()) so the app works regardless of CWD.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from assistant_bird.app_dir import get_app_dir, get_config_path


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_config_path(".env"),
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
    workspace_root: Path = Field(
        default_factory=lambda: get_app_dir() / "workspace"
    )

    # Data paths
    chroma_persist_dir: Path = Field(
        default_factory=lambda: get_app_dir() / "data" / "chroma"
    )
    sqlite_db_path: Path = Field(
        default_factory=lambda: get_app_dir() / "data" / "conversations.db"
    )
    checkpoint_db_path: Path = Field(
        default_factory=lambda: get_app_dir() / "data" / "checkpoints.db"
    )

    # Logging
    log_level: str = "INFO"

    # LLM parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Graph execution
    graph_recursion_limit: int = 60

    # Context window management
    context_max_turns: int = 30
    context_max_tokens: int = 40000
    context_keep_recent: int = 5
    context_summary_max_tokens: int = 2048


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
