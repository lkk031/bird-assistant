"""Quart application factory for the desktop server.

Creates an ASGI app with SSE-capable routes for the chat frontend.
The server runs on localhost only — no external network access.
"""

from pathlib import Path

from quart import Quart

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# Path to the desktop frontend directory
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "desktop"


def create_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart("assistant_bird")

    # Register routes
    _register_routes(app)
    _register_static(app)

    return app


def _register_routes(app: Quart) -> None:
    """Register all API and page routes."""
    from assistant_bird.server.routes import (
        handle_chat,
        handle_export,
        handle_get_messages,
        handle_list_conversations,
        handle_new_conversation,
        handle_switch_conversation,
    )

    # API
    app.add_url_rule("/chat", "chat", handle_chat, methods=["POST"])
    app.add_url_rule("/conversations", "list_conversations",
                     handle_list_conversations, methods=["GET"])
    app.add_url_rule("/conversations/new", "new_conversation",
                     handle_new_conversation, methods=["POST"])
    app.add_url_rule("/conversations/switch", "switch_conversation",
                     handle_switch_conversation, methods=["POST"])
    app.add_url_rule("/messages/<thread_id>", "get_messages",
                     handle_get_messages, methods=["GET"])
    app.add_url_rule("/export/<thread_id>", "export",
                     handle_export, methods=["GET"])
    app.add_url_rule("/health", "health",
                     lambda: ("OK", 200), methods=["GET"])

    # Page — serve index.html at /
    @app.route("/")
    async def index():
        return await app.send_static_file("index.html")


def _register_static(app: Quart) -> None:
    """Serve frontend static files (CSS, JS)."""
    # Quart serves static files from the app's static_folder
    app.static_folder = str(_FRONTEND_DIR)

    logger.info("server: static files served from", path=str(_FRONTEND_DIR))
