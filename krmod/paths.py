"""Locations of the game, the repo and the app's own folders."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

EXE_NAME = "Kingdom Rush Genesis.exe"
LUA_DLL_NAME = "lua51.dll"
SETTINGS_NAME = "settings.json"
# The single-file exe unpacks itself here, next to the exe (scripts/build.bat --runtime-tmpdir).
RUNTIME_DIR_NAME = "runtime"


class GameNotFoundError(Exception):
    """The game folder or one of the files needed from it is missing."""


def default_repo_dir() -> Path:
    """The app folder: the repo root from source, the exe's own folder when frozen.

    Profiles, settings.json and the cache live here, so the single-file exe can be copied
    anywhere (best: its own folder inside the game folder) and keeps its data beside it.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def remove_stale_runtime(repo_dir: Path, current: Path | None) -> list[str]:
    """Delete unpacked copies the single-file exe left in <repo_dir>/runtime after a crash or a
    forced kill (a normal close removes its own). current is this run's copy (sys._MEIPASS).

    A copy still used by another open instance has open files, so Windows refuses to rename
    it: rename first and only delete what could be renamed, never a half of a running copy.
    Returns the names removed.
    """
    removed: list[str] = []
    runtime = repo_dir / RUNTIME_DIR_NAME
    if not runtime.is_dir():
        return removed
    keep = current.resolve() if current else None
    for folder in runtime.glob("_MEI*"):
        if not folder.is_dir() or folder.resolve() == keep:
            continue
        doomed = folder.with_name(folder.name + ".old")
        try:
            folder.rename(doomed)
        except OSError:
            continue
        shutil.rmtree(doomed, ignore_errors=True)
        removed.append(folder.name)
    return removed


def load_settings(repo_dir: Path) -> dict[str, Any]:
    """All keys of <repo_dir>/settings.json; a missing or corrupt file counts as empty."""
    try:
        data = json.loads((repo_dir / SETTINGS_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(repo_dir: Path, **values: Any) -> None:
    """Set the given keys in <repo_dir>/settings.json and keep every other key."""
    from krmod.modgen.writer import atomic_write  # imported late: the writer imports this module

    data = load_settings(repo_dir)
    data.update(values)
    atomic_write(repo_dir / SETTINGS_NAME, json.dumps(data, indent=2) + "\n")


def load_game_dir_setting(repo_dir: Path) -> Path | None:
    """The game folder saved in <repo_dir>/settings.json; a missing or corrupt file means none."""
    game_dir = load_settings(repo_dir).get("game_dir")
    if not isinstance(game_dir, str) or not game_dir.strip():
        return None
    return Path(game_dir)


def save_game_dir_setting(repo_dir: Path, game_dir: Path) -> None:
    save_settings(repo_dir, game_dir=str(Path(game_dir).resolve()))


def load_cards_folded(repo_dir: Path) -> bool:
    """Whether the card list was left folded; anything but a saved true means unfolded."""
    return load_settings(repo_dir).get("cards_folded") is True


def save_cards_folded(repo_dir: Path, folded: bool) -> None:
    save_settings(repo_dir, cards_folded=folded)


def validate_game_dir(game_dir: Path) -> None:
    """Raise GameNotFoundError unless game_dir holds the game exe and lua51.dll."""
    if not game_dir.is_dir():
        raise GameNotFoundError(f"Game folder not found: {game_dir}")
    for name in (EXE_NAME, LUA_DLL_NAME):
        if not (game_dir / name).is_file():
            raise GameNotFoundError(f"Game file not found: {game_dir / name}")


@dataclass(frozen=True)
class GamePaths:
    game_dir: Path
    exe: Path
    lua_dll: Path
    mods_dir: Path
    repo_dir: Path
    profiles_dir: Path
    cache_dir: Path
    mod_template_dir: Path

    @cached_property
    def portraits_dir(self) -> Path:
        """Portrait cache of this game folder; every folder has its own, so switching is safe."""
        key = hashlib.sha1(str(self.game_dir.resolve()).lower().encode("utf-8")).hexdigest()[:12]
        return self.cache_dir / "portraits" / key

    @classmethod
    def for_game_dir(cls, game_dir: Path, repo_dir: Path) -> GamePaths:
        frozen = getattr(sys, "frozen", False)
        template = Path(sys._MEIPASS) / "mod_template" if frozen else repo_dir / "mod_template"
        return cls(
            game_dir=game_dir,
            exe=game_dir / EXE_NAME,
            lua_dll=game_dir / LUA_DLL_NAME,
            mods_dir=game_dir / "mods",
            repo_dir=repo_dir,
            profiles_dir=repo_dir / "profiles",
            cache_dir=repo_dir / "cache",
            mod_template_dir=template,
        )

    @classmethod
    def locate(cls, repo_dir: Path | None = None) -> GamePaths:
        """Game folder: env KRMOD_GAME_DIR, else the saved setting, else the app folder's parent."""
        if repo_dir is None:
            repo_dir = default_repo_dir()
        env_dir = os.environ.get("KRMOD_GAME_DIR")
        game_dir = Path(env_dir) if env_dir else load_game_dir_setting(repo_dir) or repo_dir.parent
        validate_game_dir(game_dir)
        return cls.for_game_dir(game_dir, repo_dir)
