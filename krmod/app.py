"""Application entry point and native window launcher."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from krmod.paths import default_repo_dir, remove_stale_runtime  # does not import nicegui

# Compute cache directory and set NICEGUI_STORAGE_PATH before importing nicegui:
_repo_dir = default_repo_dir()
_cache_dir = _repo_dir / "cache"
_nicegui_storage = _cache_dir / "nicegui"
_nicegui_storage.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NICEGUI_STORAGE_PATH", str(_nicegui_storage))

# A windowed exe has no console, so errors would vanish. Send them to cache\app.log.
if sys.stdout is None or sys.stderr is None:
    _log = open(_cache_dir / "app.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log
    print(f"KrGenesis Mod started, pid {os.getpid()}")

# The single-file exe unpacks into runtime\ next to it; clear copies a crash or kill left behind.
if getattr(sys, "frozen", False):
    for _name in remove_stale_runtime(_repo_dir, Path(getattr(sys, "_MEIPASS", ""))):
        print(f"removed stale runtime copy {_name}")

from nicegui import app as nicegui_app, ui  # noqa: E402

from krmod.gamedata.reader import ReaderError  # noqa: E402
from krmod.gameload import load_game  # noqa: E402
from krmod.paths import GameNotFoundError, GamePaths  # noqa: E402
from krmod.profiles import ProfileStore  # noqa: E402
from krmod.state import AppState  # noqa: E402
from krmod.ui.main import build_page  # noqa: E402


def load_state(repo_dir: Path | None = None) -> tuple[AppState | None, str | None]:
    """Locate game paths, read balance, build index and profile store."""
    try:
        paths = GamePaths.locate(repo_dir=repo_dir)
        tree, index = load_game(paths)
        store = ProfileStore(paths.profiles_dir)
        return AppState(paths, tree, index, store), None
    except (GameNotFoundError, ReaderError) as exc:
        return None, str(exc)


WEBVIEW2_ARGS_ENV = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
# Edge WebView2 otherwise downloads components this app never uses into cache\webview
# (video DRM, ad-filter lists, speech recognition, hyphenation: about 40 MB) and phones home.
LEAN_WEBVIEW_FLAGS = ("--disable-component-update", "--disable-background-networking")


def lean_webview_args(existing: str) -> str:
    """existing WebView2 browser arguments plus LEAN_WEBVIEW_FLAGS, each flag once."""
    args = existing.split()
    args += [flag for flag in LEAN_WEBVIEW_FLAGS if flag not in args]
    return " ".join(args)


def main() -> None:
    """Launch the KrGenesis Mod application."""
    webview_storage = _cache_dir / "webview"
    webview_storage.mkdir(parents=True, exist_ok=True)
    nicegui_app.native.start_args["storage_path"] = str(webview_storage)
    nicegui_app.native.start_args["private_mode"] = False
    # Set before ui.run starts the window process, which inherits the environment.
    os.environ[WEBVIEW2_ARGS_ENV] = lean_webview_args(os.environ.get(WEBVIEW2_ARGS_ENV, ""))
    # The layout holds down to 800 x 500 (two-row top bar, scrolling editor): no smaller window.
    nicegui_app.native.window_args["min_size"] = (800, 500)
    # Window connection events in app.log help diagnose a window that stops responding.
    nicegui_app.on_connect(lambda client: print(f"{time.strftime('%H:%M:%S')} window connected {client.id}"))
    nicegui_app.on_disconnect(lambda client: print(f"{time.strftime('%H:%M:%S')} window disconnected {client.id}"))

    state, error_msg = load_state()
    build_page(state, error_msg, repo_dir=_repo_dir)
    ui.run(
        native=True,
        reload=False,
        host="127.0.0.1",
        title="KrGenesis Mod",
        window_size=(1440, 900),
        dark=None,
    )
