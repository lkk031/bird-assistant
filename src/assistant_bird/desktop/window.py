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

from assistant_bird.app_dir import get_app_dir
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

# PID lock file — prevents multiple instances from racing on startup
_LOCK_FILE = get_app_dir() / ".app.lock"


def _acquire_lock() -> bool:
    """Try to acquire the single-instance lock. Returns True on success."""
    if _LOCK_FILE.exists():
        try:
            old_pid = int(_LOCK_FILE.read_text().strip())
            # Check if the old process is still alive
            os.kill(old_pid, 0)  # signal 0 = just check existence
            logger.info("desktop: another instance is already running",
                       pid=old_pid)
            return False
        except (ValueError, OSError):
            # PID file is stale — old process is dead
            _LOCK_FILE.unlink(missing_ok=True)

    _LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    """Release the single-instance lock."""
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


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


# JS injected into every external page to provide back/forward/home navigation.
# The toolbar hides itself when navigating back to the chat (localhost origin).
_INJECT_NAV_BAR = r"""
(function () {
  if (document.getElementById('__ab_navbar__')) return;  // already injected
  if (window.location.hostname === 'localhost') return;   // chat page, skip

  var bar = document.createElement('div');
  bar.id = '__ab_navbar__';
  bar.innerHTML =
    '<button id="__ab_back__" title="后退 (Alt+←)">◀</button>' +
    '<button id="__ab_fwd__" title="前进 (Alt+→)">▶</button>' +
    '<button id="__ab_home__" title="返回鸟助手">🏠 返回聊天</button>' +
    '<span id="__ab_url__"></span>';
  bar.setAttribute('style',
    'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
    'display:flex;align-items:center;gap:4px;padding:6px 10px;' +
    'background:#1e1f29;border-bottom:1px solid #3a3b47;' +
    'font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;'
  );

  var back = bar.querySelector('#__ab_back__');
  var fwd  = bar.querySelector('#__ab_fwd__');
  var home = bar.querySelector('#__ab_home__');
  var urlSpan = bar.querySelector('#__ab_url__');

  var style = document.createElement('style');
  style.textContent =
    '#__ab_navbar__ button{padding:4px 10px;border:1px solid #3a3b47;' +
    'border-radius:3px;background:transparent;color:#9e9eae;cursor:pointer;}' +
    '#__ab_navbar__ button:hover{background:#2a2b37;color:#e8e8ed;}' +
    '#__ab_navbar__ button:disabled{opacity:0.3;cursor:default;}' +
    '#__ab_navbar__ #__ab_url__{flex:1;margin-left:8px;color:#6b6b7b;' +
    'font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
    'body{padding-top:36px !important;}';  // push content down

  document.head.appendChild(style);
  document.body.insertBefore(bar, document.body.firstChild);
  document.body.style.paddingTop = '36px';

  urlSpan.textContent = window.location.href;

  back.addEventListener('click', function(){window.history.back();});
  fwd.addEventListener('click', function(){window.history.forward();});
  home.addEventListener('click', function(){
    window.location.href = 'http://localhost:19900';
  });

  // Remove bar when returning to chat (popstate fires on back/forward)
  window.addEventListener('popstate', function(){
    if (window.location.hostname === 'localhost') {
      var b = document.getElementById('__ab_navbar__');
      if (b) { b.remove(); document.body.style.paddingTop = ''; }
    }
  });
})();
"""


def start_desktop(dev_mode: bool = False) -> None:
    """Start the desktop application.

    Args:
        dev_mode: If True, open in the default browser instead of a
                  pywebview window. Useful for UI development.
    """
    url = f"http://localhost:{DEFAULT_PORT}"

    # Single-instance lock — refuse to start if already running
    if not _acquire_lock():
        print("⚠️  鸟助手已在运行中，请查看系统托盘或窗口。")
        sys.exit(0)

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
            window = webview.create_window(
                title=WINDOW_TITLE,
                url=url,
                width=DEFAULT_WIDTH,
                height=DEFAULT_HEIGHT,
                min_size=(MIN_WIDTH, MIN_HEIGHT),
                text_select=True,
            )

            # Inject navigation bar on every page load so external pages
            # get back/forward/home buttons injected directly into their DOM.
            #
            # IMPORTANT: cannot call window.evaluate_js() directly from the
            # loaded handler — it uses glib.idle_add + a blocking semaphore,
            # which deadlocks when the handler runs on the GTK main thread.
            # Instead, spawn a daemon thread that waits briefly for GTK to
            # finish processing the load event, then injects the JS.
            def _inject_nav_async():
                try:
                    time.sleep(0.3)  # let GTK finish current event
                    window.evaluate_js(_INJECT_NAV_BAR)
                except Exception:
                    pass  # best-effort

            def on_loaded():
                import threading
                threading.Thread(
                    target=_inject_nav_async, daemon=True,
                ).start()

            window.events.loaded += on_loaded

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
        _release_lock()
