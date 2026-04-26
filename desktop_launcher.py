"""Desktop launcher for CAD Eval web UI.

Starts the local UI server and opens the browser automatically.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from src.web_ui import run_server


def _bundle_root() -> Path:
    """Return PyInstaller extraction root (or source root when not frozen)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def _runtime_root() -> Path:
    """Return a writable runtime root directory for settings/data/output."""
    if getattr(sys, "frozen", False):
        root = Path.home() / "CAD-Eval"
    else:
        root = Path(__file__).resolve().parent
    root.mkdir(parents=True, exist_ok=True)
    return root


def _bootstrap_runtime_files(runtime_root: Path) -> None:
    """Populate runtime root with bundled runtime assets on first run."""
    bundle_root = _bundle_root()

    src_env = bundle_root / ".env"
    dst_env = runtime_root / ".env"
    if src_env.exists() and not dst_env.exists():
        shutil.copy2(src_env, dst_env)

    src_credentials = bundle_root / "credentials"
    dst_credentials = runtime_root / "credentials"
    if src_credentials.exists() and not dst_credentials.exists():
        shutil.copytree(src_credentials, dst_credentials)

    src_data = bundle_root / "data"
    dst_data = runtime_root / "data"
    bundled_dxf_dir = src_data / "dxf"
    runtime_dxf_dir = dst_data / "dxf"
    if bundled_dxf_dir.exists() and not any(runtime_dxf_dir.rglob("*.dxf")):
        shutil.copytree(bundled_dxf_dir, runtime_dxf_dir, dirs_exist_ok=True)

    bundled_images_dir = src_data / "images"
    runtime_images_dir = dst_data / "images"
    if bundled_images_dir.exists() and not any(runtime_images_dir.rglob("*")):
        shutil.copytree(bundled_images_dir, runtime_images_dir, dirs_exist_ok=True)

    # Ensure expected directories exist even if no credentials are bundled.
    dst_credentials.mkdir(parents=True, exist_ok=True)
    dst_data.mkdir(parents=True, exist_ok=True)
    (runtime_root / "output").mkdir(parents=True, exist_ok=True)


def _find_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
    """Return an available port near preferred_port."""
    for offset in range(max_tries + 1):
        port = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found starting from {preferred_port}")


def main() -> None:
    runtime_root = _runtime_root()
    _bootstrap_runtime_files(runtime_root)
    os.environ.setdefault("CAD_EVAL_PROJECT_ROOT", str(runtime_root))

    host = os.getenv("CAD_EVAL_UI_HOST", "127.0.0.1")
    preferred_port = int(os.getenv("CAD_EVAL_UI_PORT", "8080"))
    port = _find_available_port(host, preferred_port)
    url = f"http://{host}:{port}"

    def _open_browser() -> None:
        # Give the HTTP server a moment to start accepting connections.
        time.sleep(1.2)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()
    run_server(host=host, port=port)


if __name__ == "__main__":
    main()
