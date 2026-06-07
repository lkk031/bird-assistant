"""Desktop window management via pywebview.

Starts the Quart server in a background thread and opens a native OS
window displaying the chat UI. Supports a --dev mode for browser-based
development.
"""

import sys
import threading

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

WINDOW_TITLE = "鸟助手 (Assistant-Bird)"
DEFAULT_PORT = 19900
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WIDTH = 800
MIN_HEIGHT = 600


def start_desktop(dev_mode: bool = False) -> None:
    """Start the desktop application.

    Args:
        dev_mode: If True, open in the default browser instead of a
                  pywebview window. Useful for UI development.
    """
    from assistant_bird.graph.builder import build_assistant_graph
    from assistant_bird.llm.deepseek import create_deepseek_model
    from assistant_bird.server.app import create_app
    from assistant_bird.server.session import get_session

    # Initialize the backend session
    session = get_session()
    model = create_deepseek_model()
    session.model = model

    # Build the agent graph (this is the expensive step)
    logger.info("desktop: building agent graph...")
    import asyncio
    loop = asyncio.new_event_loop()
    app_graph = loop.run_until_complete(build_assistant_graph(model))
    loop.close()
    session.app = app_graph
    logger.info("desktop: agent graph ready")

    # Create the Quart web app
    web_app = create_app()

    # Start Quart server in a background thread
    def run_server():
        import asyncio as _asyncio
        import logging

        # Suppress hypercorn access logs unless debugging
        logging.getLogger("hypercorn.access").setLevel(logging.WARNING)

        _asyncio.run(
            web_app.run_task(
                host="127.0.0.1",
                port=DEFAULT_PORT,
                shutdown_trigger=lambda: None,  # Never auto-shutdown
            )
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    url = f"http://localhost:{DEFAULT_PORT}"

    if dev_mode:
        import webbrowser
        logger.info("desktop: opening in browser (dev mode)", url=url)
        webbrowser.open(url)
        # Keep the main thread alive
        try:
            server_thread.join()
        except KeyboardInterrupt:
            logger.info("desktop: shutting down")
    else:
        try:
            import webview
        except ImportError:
            logger.error(
                "desktop: pywebview not installed. "
                "Install with: pip install pywebview\n"
                "For Linux you may need: sudo apt install "
                "python3-gi gir1.2-webkit2-4.0"
            )
            print(
                "\n⚠️  pywebview 未安装。使用 --dev 模式在浏览器中运行。\n"
                "    Linux 依赖: sudo apt install python3-gi gir1.2-webkit2-4.0\n"
            )
            sys.exit(1)

        logger.info("desktop: opening window", url=url)
        webview.create_window(
            title=WINDOW_TITLE,
            url=url,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_size=(MIN_WIDTH, MIN_HEIGHT),
            text_select=True,
        )
        webview.start(gui="gtk" if sys.platform == "linux" else None)
