from pathlib import Path

import pytest

import krmod
from krmod.paths import GameNotFoundError, GamePaths


def test_locate_finds_game(game_paths):
    assert game_paths.exe.name == "Kingdom Rush Genesis.exe"
    assert game_paths.mods_dir == game_paths.game_dir / "mods"
    assert game_paths.repo_dir == Path(krmod.__file__).resolve().parents[1]


def test_locate_missing_exe(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "kingdomrush-data-mod"
    repo.mkdir()
    with pytest.raises(GameNotFoundError, match="Kingdom Rush Genesis.exe"):
        GamePaths.locate(repo)
