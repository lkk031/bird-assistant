"""Assistant-Bird entry point — desktop and CLI launcher.

Usage:
    poetry run assistant-bird              # Desktop window (pywebview)
    poetry run assistant-bird --dev        # Open in browser (development)
    poetry run python -m assistant_bird.main --dev
"""

from assistant_bird.logging_config import setup_logging


def run() -> None:
    """CLI entry point (invoked via `poetry run assistant-bird`)."""
    setup_logging()

    import argparse

    parser = argparse.ArgumentParser(
        description="🐦 鸟助手 (Assistant-Bird) — Multi-Agent AI Assistant"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Open in browser instead of desktop window (for development)",
    )
    args = parser.parse_args()

    from assistant_bird.desktop.window import start_desktop

    print("🐦 Assistant-Bird (鸟助手) v0.2.0")
    if args.dev:
        print("Development mode — opening in browser")
    else:
        print("Starting desktop window...")
    print()

    start_desktop(dev_mode=args.dev)


if __name__ == "__main__":
    run()
