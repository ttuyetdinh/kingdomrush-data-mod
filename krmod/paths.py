"""Locations of the game, the repo and the app's own folders."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

EXE_NAME = "Kingdom Rush Genesis.exe"
LUA_DLL_NAME = "lua51.dll"


class GameNotFoundError(Exception):
    """The game folder or one of the files needed from it is missing."""


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
        if repo_dir is None:
            if getattr(sys, "frozen", False):
                repo_dir = Path(sys.executable).resolve().parents[2]
            else:
                repo_dir = Path(__file__).resolve().parents[1]
        env_dir = os.environ.get("KRMOD_GAME_DIR")
        game_dir = Path(env_dir) if env_dir else repo_dir.parent
        paths = cls.for_game_dir(game_dir, repo_dir)
        for required in (paths.exe, paths.lua_dll):
            if not required.is_file():
                raise GameNotFoundError(f"Game file not found: {required}")
        return paths
