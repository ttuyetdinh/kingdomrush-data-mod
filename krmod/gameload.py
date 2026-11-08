"""Reading a game folder into the data the app needs (balance tree and group index)."""
from __future__ import annotations

import threading
from pathlib import Path

from krmod.assets.portraits import build_portrait_cache
from krmod.gamedata.reader import read_balance
from krmod.model.grouping import GroupIndex
from krmod.model.values import BalanceTree
from krmod.paths import GamePaths, validate_game_dir


def load_game(paths: GamePaths) -> tuple[BalanceTree, GroupIndex]:
    """Read the balance data of paths.game_dir and start building its portrait cache.

    Raises ReaderError when the game files cannot be read.
    """
    tree = read_balance(paths)
    index = GroupIndex.build(tree)
    threading.Thread(target=build_portrait_cache, args=(paths,), daemon=True).start()
    return tree, index


def open_game_dir(game_dir: Path, repo_dir: Path) -> tuple[GamePaths, BalanceTree, GroupIndex]:
    """Validate a user-chosen folder and read it; raises GameNotFoundError or ReaderError."""
    validate_game_dir(game_dir)
    paths = GamePaths.for_game_dir(game_dir, repo_dir)
    tree, index = load_game(paths)
    return paths, tree, index
