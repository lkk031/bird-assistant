"""Quart application factory for the desktop server.

Creates an ASGI app with SSE-capable routes for the chat frontend.
The server runs on localhost only — no external network access.

On startup, initializes the LLM model and LangGraph agent graph
so they're ready before the first request arrives.
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

    # Initialize backend on startup
    @app.before_serving
    async def startup():
        """Initialize the LLM model and agent graph before serving requests."""
        from assistant_bird.graph.builder import build_assistant_graph
        from assistant_bird.llm.deepseek import create_deepseek_model
        from assistant_bird.server.session import get_session

        logger.info("server: initializing model and agent graph (before_serving)...")
        session = get_session()
        session.model = create_deepseek_model()
        session.app = await build_assistant_graph(session.model)
        logger.info("server: startup complete — ready to accept connections")

    return app


def _register_routes(app: Quart) -> None:
    """Register all API and page routes."""
    from assistant_bird.server.routes import (
        handle_chat,
        handle_delete_conversation,
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
    app.add_url_rule("/conversations/<thread_id>", "delete_conversation",
                     handle_delete_conversation, methods=["DELETE"])
    app.add_url_rule("/health", "health",
                     _health_check, methods=["GET"])

    # Page — serve index.html at /
    @app.route("/")
    async def index():
        return await app.send_static_file("index.html")


def _register_static(app: Quart) -> None:
    """Serve frontend static files (CSS, JS)."""
    app.static_folder = str(_FRONTEND_DIR)
    logger.info("server: static files served from", path=str(_FRONTEND_DIR))


async def _health_check():
    """Health check that verifies the agent graph is ready."""
    from assistant_bird.server.session import get_session

    session = get_session()
    if session.app is not None:
        return ("OK", 200)
    return ("Initializing...", 503)
