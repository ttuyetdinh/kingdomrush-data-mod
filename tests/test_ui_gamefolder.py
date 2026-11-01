import json
import os
import sys

import pytest
from nicegui.testing.user_simulation import user_simulation

from krmod.paths import load_game_dir_setting


def _main_file(tmp_path, body: str):
    main_file = tmp_path / "gamefolder_main.py"
    main_file.write_text(
        "from pathlib import Path\n"
        "from nicegui import core, ui\n"
        "from krmod.app import load_state\n"
        "from krmod.ui.main import build_page\n"
        "core.reset()\n" + body + "ui.run()\n",
        encoding="utf-8",
    )
    return main_file


@pytest.fixture
async def user_no_game(tmp_path, monkeypatch):
    """Error page: the repo folder's parent is no game folder and nothing is saved."""
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "game" / "repo"
    repo.mkdir(parents=True)
    main_file = _main_file(
        tmp_path,
        f"repo = Path({str(repo)!r})\n"
        "state, err = load_state(repo_dir=repo)\n"
        "assert state is None\n"
        "build_page(state, err, repo_dir=repo)\n",
    )
    async with user_simulation(main_file=main_file) as u:
        u.repo = repo
        yield u


async def test_error_page_offers_folder_choice(user_no_game):
    await user_no_game.open("/")
    await user_no_game.should_see("Kingdom Rush Genesis.exe")
    await user_no_game.should_see("Choose game folder")
    await user_no_game.should_see(marker="game-dir-input")


async def test_error_page_invalid_folder_notifies(user_no_game, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    await user_no_game.open("/")
    user_no_game.find(marker="game-dir-input").type(str(empty))
    user_no_game.find(marker="btn-use-game-folder").click()
    await user_no_game.should_see("Kingdom Rush Genesis.exe")
    assert user_no_game.notify.contains("Game file not found")
    await user_no_game.should_see(marker="game-dir-input")
    assert load_game_dir_setting(user_no_game.repo) is None


async def test_error_page_empty_input_notifies(user_no_game):
    await user_no_game.open("/")
    user_no_game.find(marker="btn-use-game-folder").click()
    assert user_no_game.notify.contains("Enter the path")


async def test_error_page_valid_folder_loads_editor(user_no_game, game_paths):
    await user_no_game.open("/")
    user_no_game.find(marker="game-dir-input").type(str(game_paths.game_dir))
    user_no_game.find(marker="btn-use-game-folder").click()
    await user_no_game.should_see("5857/5857 values placed")
    assert load_game_dir_setting(user_no_game.repo) == game_paths.game_dir.resolve()
    saved = json.loads((user_no_game.repo / "settings.json").read_text(encoding="utf-8"))
    assert saved == {"game_dir": str(game_paths.game_dir.resolve())}


async def test_topbar_switch_keeps_profile_and_uses_new_paths(tmp_path, monkeypatch, game_paths):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "game" / "repo"
    repo.mkdir(parents=True)
    # Start on the real game folder via a saved setting, with profiles kept in the temp repo.
    (repo / "settings.json").write_text(
        json.dumps({"game_dir": str(game_paths.game_dir)}), encoding="utf-8"
    )
    main_file = _main_file(
        tmp_path,
        f"repo = Path({str(repo)!r})\n"
        "state, err = load_state(repo_dir=repo)\n"
        "assert err is None, err\n"
        "build_page(state, err, repo_dir=repo)\n",
    )
    async with user_simulation(main_file=main_file) as u:
        await u.open("/")
        await u.should_see("5857/5857 values placed")
        u.find(marker="profile-menu").click()
        u.find("New").click()
        u.find(marker="profile-name").type("Keep")
        u.find("Create").click()
        u.find(marker="profile-menu").click()
        u.find(marker="profile-item-keep").click()

        u.find(marker="game-folder").click()
        empty = tmp_path / "empty"
        empty.mkdir()
        u.find(marker="game-dir-input").clear()
        u.find(marker="game-dir-input").type(str(empty))
        u.find(marker="btn-use-game-folder").click()
        assert u.notify.contains("Game file not found")

        # A second valid folder: hard links to the real exe and dll.
        other = tmp_path / "other_game"
        other.mkdir()
        try:
            for src in (game_paths.exe, game_paths.lua_dll):
                os.link(src, other / src.name)
        except OSError as exc:
            pytest.skip(f"cannot hard link game files: {exc}")
        u.find(marker="game-dir-input").clear()
        u.find(marker="game-dir-input").type(str(other))
        u.find(marker="btn-use-game-folder").click()
        await u.should_see("5857/5857 values placed")
        await u.should_see("Keep")
        # nicegui drops krmod.ui.main from sys.modules between simulations, so look it up now.
        ui_main = sys.modules["krmod.ui.main"]
        paths = ui_main._active_state.paths
        assert paths.game_dir == other.resolve()
        assert paths.mods_dir == other.resolve() / "mods"
        assert paths.portraits_dir != game_paths.portraits_dir
        assert ui_main._active_state.profile.name == "Keep"
        assert load_game_dir_setting(repo) == other.resolve()
