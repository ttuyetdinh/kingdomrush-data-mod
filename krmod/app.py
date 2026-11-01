"""Application entry point and native window launcher."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Compute cache directory and set NICEGUI_STORAGE_PATH before importing nicegui:
if getattr(sys, "frozen", False):
    _repo_dir = Path(sys.executable).resolve().parents[2]
else:
    _repo_dir = Path(__file__).resolve().parents[1]
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


def main() -> None:
    """Launch the KrGenesis Mod application."""
    webview_storage = _cache_dir / "webview"
    webview_storage.mkdir(parents=True, exist_ok=True)
    nicegui_app.native.start_args["storage_path"] = str(webview_storage)
    nicegui_app.native.start_args["private_mode"] = False

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
