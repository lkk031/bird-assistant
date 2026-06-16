"""Desktop window management via pywebview.

Starts the Quart server as a subprocess and opens a native OS window
displaying the chat UI. Supports a --dev mode for browser-based
development.

On Python 3.13+, asyncio signal handlers cannot be registered from
background threads, so we run hypercorn in its own process.
"""

import os
import signal
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


def _kill_existing_server(port: int) -> None:
    """Kill any process already listening on the given port."""
    # Prefer ss over lsof/fuser — always available on modern Linux
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if f":{port}" not in line:
                continue
            # Extract PID from ss output: ...pid=12345,...
            parts = line.split()
            for p in parts:
                if "pid=" in p:
                    pid_str = p.split("pid=")[-1].rstrip(",")
                    try:
                        pid = int(pid_str)
                        logger.info(
                            "desktop: killing old server",
                            pid=pid, port=port,
                        )
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(0.5)
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            pass  # already dead
                    except (ValueError, OSError):
                        pass
    except Exception:
        pass


def _cleanup_server(proc: subprocess.Popen) -> None:
    """Ensure the hypercorn subprocess and all its children are terminated."""
    if proc is None or proc.poll() is not None:
        return
    logger.info("desktop: cleaning up server process", pid=proc.pid)
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            logger.warning("desktop: server didn't stop, force killing")
            proc.kill()
            proc.wait(timeout=2)
    except Exception:
        logger.exception("desktop: cleanup error — attempting force kill")
        try:
            proc.kill()
        except Exception:
            pass


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

    # Kill any lingering server from a previous crashed session.
    # This ensures the app can restart after an unclean exit.
    _kill_existing_server(DEFAULT_PORT)

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

    try:
        if dev_mode:
            import webbrowser

            logger.info("desktop: opening in browser (dev mode)", url=url)
            print(f"\n🌐 浏览器模式: {url}\n按 Ctrl+C 退出\n")
            webbrowser.open(url)
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
            logger.info("desktop: window closed normally")
    except KeyboardInterrupt:
        logger.info("desktop: interrupted by user")
    except Exception:
        logger.exception("desktop: window error")
    finally:
        # Always clean up the server subprocess — even if the window
        # crashed or webview.start() threw an exception. Without this,
        # the hypercorn process stays alive and blocks port 19900,
        # preventing subsequent launches.
        _cleanup_server(server_proc)
