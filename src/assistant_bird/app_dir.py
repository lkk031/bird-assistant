"""Application data directory resolution.

Provides a platform-appropriate user data directory for storing
configuration, databases, and conversation history independent of
the current working directory.

Linux:   ~/.local/share/assistant-bird/
macOS:   ~/Library/Application Support/assistant-bird/
Windows: %APPDATA%/assistant-bird/
"""

from pathlib import Path

from platformdirs import user_data_dir


def get_app_dir() -> Path:
    """Return the per-user application data directory, creating it if needed."""
    path = Path(user_data_dir("assistant-bird", ensure_exists=True))
    subdirs = ["data", "data/chroma", "workspace"]
    for sub in subdirs:
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def get_config_path(filename: str = ".env") -> Path:
    """Return the path to a config file in the app directory.

    Falls back to the current working directory if the file exists there
    (for backward compatibility with existing installations).
    """
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
    return get_app_dir() / filename
