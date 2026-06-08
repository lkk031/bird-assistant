"""Desktop window management via pywebview.

Starts the Quart server as a subprocess and opens a native OS window
displaying the chat UI. Supports a --dev mode for browser-based
development.

On Python 3.13+, asyncio signal handlers cannot be registered from
background threads, so we run hypercorn in its own process.
"""

import subprocess
import sys
import time

from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

WINDOW_TITLE = "鸟助手 (Assistant-Bird)"
DEFAULT_PORT = 19900
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WIDTH = 800
MIN_HEIGHT = 600

# Module path for hypercorn to load the Quart app
APP_MODULE = "assistant_bird.server.app:create_app()"


def _wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Poll the health endpoint until the server is ready."""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(f"{url}/health", timeout=0.5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def start_desktop(dev_mode: bool = False) -> None:
    """Start the desktop application.

    Args:
        dev_mode: If True, open in the default browser instead of a
                  pywebview window. Useful for UI development.
    """
    url = f"http://localhost:{DEFAULT_PORT}"

    # Start the Quart server as a subprocess so that asyncio signal
    # handlers work correctly (hypercorn requires the main thread).
    logger.info("desktop: starting server subprocess", port=DEFAULT_PORT)

    server_proc = subprocess.Popen(
        [
            sys.executable, "-m", "hypercorn",
            "--bind", f"127.0.0.1:{DEFAULT_PORT}",
            "--workers", "1",
            "--access-logfile", "-" if dev_mode else "/dev/null",
            APP_MODULE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for the server to be ready
    logger.info("desktop: waiting for server to be ready...")
    if not _wait_for_server(url, timeout=45.0):
        logger.error("desktop: server failed to start within timeout")
        server_proc.kill()
        server_proc.wait()
        print("\n⚠️  服务器启动超时，请检查 DeepSeek API Key 是否已配置。")
        sys.exit(1)

    logger.info("desktop: server ready", url=url)

    if dev_mode:
        import webbrowser

        logger.info("desktop: opening in browser (dev mode)", url=url)
        print(f"\n🌐 浏览器模式: {url}\n按 Ctrl+C 退出\n")
        webbrowser.open(url)

        try:
            server_proc.wait()
        except KeyboardInterrupt:
            logger.info("desktop: shutting down")
            server_proc.terminate()
            server_proc.wait()
    else:
        try:
            import webview
        except ImportError:
            logger.error("desktop: pywebview not installed")
            print(
                "\n⚠️  pywebview 未安装。使用 --dev 模式在浏览器中运行。\n"
                "    Linux 依赖: sudo apt install python3-gi gir1.2-webkit2-4.1\n"
            )
            server_proc.terminate()
            server_proc.wait()
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

        # Window closed — clean up server
        logger.info("desktop: window closed, stopping server")
        server_proc.terminate()
        server_proc.wait()
