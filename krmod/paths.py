"""Locations of the game, the repo and the app's own folders."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

EXE_NAME = "Kingdom Rush Genesis.exe"
LUA_DLL_NAME = "lua51.dll"
SETTINGS_NAME = "settings.json"


class GameNotFoundError(Exception):
    """The game folder or one of the files needed from it is missing."""


def default_repo_dir() -> Path:
    """The app folder: the repo root from source, three levels above the exe when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[2]
    return Path(__file__).resolve().parents[1]


def load_game_dir_setting(repo_dir: Path) -> Path | None:
    """The game folder saved in <repo_dir>/settings.json; a missing or corrupt file means none."""
    try:
        data = json.loads((repo_dir / SETTINGS_NAME).read_text(encoding="utf-8"))
        game_dir = data["game_dir"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(game_dir, str) or not game_dir.strip():
        return None
    return Path(game_dir)


def save_game_dir_setting(repo_dir: Path, game_dir: Path) -> None:
    from krmod.modgen.writer import atomic_write  # imported late: the writer imports this module

    text = json.dumps({"game_dir": str(Path(game_dir).resolve())}, indent=2)
    atomic_write(repo_dir / SETTINGS_NAME, text + "\n")


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

    @property
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
