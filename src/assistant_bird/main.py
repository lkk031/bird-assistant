"""Assistant-Bird entry point — Chainlit application runner.

Usage:
    chainlit run src/assistant_bird/main.py
    or
    poetry run assistant-bird
"""

import sys

from assistant_bird.logging_config import setup_logging


def run() -> None:
    """CLI entry point for assistant-bird (invoked via `poetry run assistant-bird`)."""
    setup_logging()

    print("🐦 Assistant-Bird (鸟助手) v0.1.0")
    print("Starting Chainlit server...")
    print()

    # Delegate to chainlit CLI
    import subprocess

    subprocess.run(
        [
            sys.executable, "-m", "chainlit", "run",
            "src/assistant_bird/main.py",
        ],
        check=False,
    )


# Chainlit auto-discovers these by importing the module.
# We import our callbacks so they register with Chainlit.
from assistant_bird.ui.callbacks import (  # noqa: E402, F401
    on_chat_end,
    on_chat_start,
    on_message,
)

# Setup logging when module is loaded
setup_logging()


if __name__ == "__main__":
    run()
