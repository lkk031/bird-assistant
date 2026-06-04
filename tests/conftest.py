"""Shared test fixtures."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure tests don't use real API keys or modify real data.

    Uses os.environ to set vars BEFORE any project imports happen,
    then clears all cached singletons so tests use the temp paths.
    """
    tmp = Path(tempfile.mkdtemp())
    os.environ["DEEPSEEK_API_KEY"] = "test-key-not-real"
    os.environ["MEM0_API_KEY"] = ""
    os.environ["LOG_LEVEL"] = "ERROR"
    os.environ["WORKSPACE_ROOT"] = str(tmp / "workspace")
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp / "chroma")
    os.environ["SQLITE_DB_PATH"] = str(tmp / "conversations.db")
    os.environ["CHECKPOINT_DB_PATH"] = str(tmp / "checkpoints.db")

    # Ensure directories exist
    (tmp / "workspace").mkdir(parents=True, exist_ok=True)
    (tmp / "chroma").mkdir(parents=True, exist_ok=True)

    # Clear all module-level singletons to pick up test env
    _clear_singletons()

    yield tmp

    # Cleanup singletons again so next test module gets fresh state
    _clear_singletons()

    # Cleanup temp dir
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    # Restore env
    for key in [
        "DEEPSEEK_API_KEY", "MEM0_API_KEY", "LOG_LEVEL",
        "WORKSPACE_ROOT", "CHROMA_PERSIST_DIR",
        "SQLITE_DB_PATH", "CHECKPOINT_DB_PATH",
    ]:
        os.environ.pop(key, None)


def _clear_singletons():
    """Clear all cached singletons so tests get fresh instances."""
    # Clear pydantic-settings cache
    from assistant_bird.config import get_settings
    get_settings.cache_clear()

    # Clear memory singletons
    import assistant_bird.memory.mem0_client as mc
    mc._mem0 = None  # type: ignore[attr-defined]

    import assistant_bird.memory.vector_store as vs
    vs._vector_store = None  # type: ignore[attr-defined]

    import assistant_bird.memory.conversation_db as cd
    cd._conversation_db = None  # type: ignore[attr-defined]

    import assistant_bird.memory.memory_manager as mm
    mm._memory_manager = None  # type: ignore[attr-defined]

    # Clear tool registry singleton
    import assistant_bird.tools.registry as tr
    tr._registry = None  # type: ignore[attr-defined]


@pytest.fixture
def workspace_dir(setup_test_env) -> Path:
    """Return the test workspace path."""
    return setup_test_env / "workspace"
