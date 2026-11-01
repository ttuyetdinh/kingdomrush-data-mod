"""Application entry point and native window launcher."""
from __future__ import annotations

import os
import sys
import threading
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

from nicegui import app as nicegui_app, ui  # noqa: E402

from krmod.assets.portraits import build_portrait_cache  # noqa: E402
from krmod.gamedata.reader import ReaderError, read_balance  # noqa: E402
from krmod.model.grouping import GroupIndex  # noqa: E402
from krmod.paths import GameNotFoundError, GamePaths  # noqa: E402
from krmod.profiles import ProfileStore  # noqa: E402
from krmod.state import AppState  # noqa: E402
from krmod.ui.main import build_page  # noqa: E402


def main() -> None:
    """Launch the KrGenesis Mod application."""
    webview_storage = _cache_dir / "webview"
    webview_storage.mkdir(parents=True, exist_ok=True)
    nicegui_app.native.start_args["storage_path"] = str(webview_storage)
    nicegui_app.native.start_args["private_mode"] = False

    state: AppState | None = None
    error_msg: str | None = None

    try:
        paths = GamePaths.locate()
        threading.Thread(target=build_portrait_cache, args=(paths,), daemon=True).start()
        tree = read_balance(paths)
        index = GroupIndex.build(tree)
        store = ProfileStore(paths.profiles_dir)
        state = AppState(paths, tree, index, store)
    except (GameNotFoundError, ReaderError) as exc:
        error_msg = str(exc)
    build_page(state, error_msg)

    ui.run(
        native=True,
        reload=False,
        host="127.0.0.1",
        title="KrGenesis Mod",
        window_size=(1440, 900),
        dark=None,
    )
