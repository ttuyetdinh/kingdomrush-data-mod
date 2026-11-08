import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from nicegui.testing.user_simulation import user_simulation

import krmod
from krmod.paths import load_game_dir_setting
from tests import fake_window

REPO_ROOT = Path(krmod.__file__).resolve().parents[1]


def _main_file(tmp_path, body: str):
    main_file = tmp_path / "gamefolder_main.py"
    main_file.write_text(
        "from pathlib import Path\n"
        "from nicegui import core, ui\n"
        "from krmod.app import load_state\n"
        "from krmod.ui.main import build_page\n"
        "from tests import fake_window\n"
        "core.reset()\n" + body + "ui.run()\n",
        encoding="utf-8",
    )
    return main_file


def _error_page_main(tmp_path, repo, native: bool):
    return _main_file(
        tmp_path,
        f"repo = Path({str(repo)!r})\n"
        + ("fake_window.app.native.main_window = fake_window.FakeWindow()\n" if native else "")
        + "state, err = load_state(repo_dir=repo)\n"
        "assert state is None\n"
        "build_page(state, err, repo_dir=repo)\n",
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "game" / "repo"
    repo.mkdir(parents=True)
    return repo


@pytest.fixture
async def user_no_game(tmp_path, repo):
    """Error page: the repo folder's parent is no game folder and nothing is saved."""
    async with user_simulation(main_file=_error_page_main(tmp_path, repo, native=False)) as u:
        u.repo = repo
        yield u


@pytest.fixture(scope="session")
def second_game():
    """A second valid game folder on the repo's drive: hard links to the real exe and dll
    (copies when linking is not possible), kept in the gitignored cache folder.

    It is not deleted afterwards: the test process keeps lua51.dll loaded, and Windows
    refuses to delete a loaded dll. It is refreshed whenever it no longer matches the game.
    """
    folder = REPO_ROOT / "cache" / "test_game"
    folder.mkdir(parents=True, exist_ok=True)
    game = REPO_ROOT.parent
    for name in ("Kingdom Rush Genesis.exe", "lua51.dll"):
        src, dst = game / name, folder / name
        if dst.exists() and os.path.samefile(src, dst):
            continue
        dst.unlink(missing_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    return folder


async def _notified(user, text: str) -> bool:
    """Handlers that read the game run off the event loop, so wait for the notification."""
    for _ in range(100):
        if user.notify.contains(text):
            return True
        await asyncio.sleep(0.05)
    return False


async def _until(condition) -> bool:
    for _ in range(200):
        if condition():
            return True
        await asyncio.sleep(0.05)
    return False


def _live_file_state(mods_dir: Path):
    live = mods_dir / "kr_mod_live.lua"
    if not live.is_file():
        return None
    return live.stat().st_mtime_ns, live.read_bytes()


async def test_error_page_offers_folder_choice(user_no_game):
    await user_no_game.open("/")
    await user_no_game.should_see("Kingdom Rush Genesis.exe")
    await user_no_game.should_see("Choose game folder")
    await user_no_game.should_see(marker="game-dir-input")


async def test_error_page_input_starts_at_repo_parent(user_no_game):
    await user_no_game.open("/")
    field = next(iter(user_no_game.find(marker="game-dir-input").elements))
    assert field.value == str(user_no_game.repo.parent)


async def test_error_page_invalid_folder_notifies(user_no_game, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    await user_no_game.open("/")
    user_no_game.find(marker="game-dir-input").clear()
    user_no_game.find(marker="game-dir-input").type(str(empty))
    user_no_game.find(marker="btn-use-game-folder").click()
    await user_no_game.should_see("Kingdom Rush Genesis.exe")
    assert await _notified(user_no_game, "Game file not found")
    await user_no_game.should_see(marker="game-dir-input")
    assert load_game_dir_setting(user_no_game.repo) is None


async def test_error_page_empty_input_notifies(user_no_game):
    await user_no_game.open("/")
    user_no_game.find(marker="game-dir-input").clear()
    user_no_game.find(marker="btn-use-game-folder").click()
    assert await _notified(user_no_game, "Enter the path")


async def test_error_page_valid_folder_loads_editor(user_no_game, game_paths):
    await user_no_game.open("/")
    user_no_game.find(marker="game-dir-input").clear()
    user_no_game.find(marker="game-dir-input").type(str(game_paths.game_dir))
    user_no_game.find(marker="btn-use-game-folder").click()
    await user_no_game.should_see("5857/5857 values placed", retries=50)
    assert load_game_dir_setting(user_no_game.repo) == game_paths.game_dir.resolve()
    saved = json.loads((user_no_game.repo / "settings.json").read_text(encoding="utf-8"))
    assert saved == {"game_dir": str(game_paths.game_dir.resolve())}


@pytest.fixture
async def user_native(tmp_path, repo, request):
    """Error page with a fake native window whose folder dialog returns request.param."""
    fake_window.install(request.param)
    try:
        async with user_simulation(main_file=_error_page_main(tmp_path, repo, native=True)) as u:
            u.repo = repo
            yield u
    finally:
        fake_window.uninstall()


@pytest.mark.parametrize("user_native", [None], indirect=True)
async def test_native_picker_cancel_changes_nothing_and_shows_input(user_native):
    await user_native.open("/")
    await user_native.should_not_see(marker="game-dir-input")
    user_native.find(marker="btn-choose-game-folder").click()
    await user_native.should_see(marker="game-dir-input")
    await user_native.should_see("Kingdom Rush Genesis.exe")
    assert len(fake_window.CALLS) == 1
    assert fake_window.CALLS[0]["directory"] == str(user_native.repo.parent)
    assert load_game_dir_setting(user_native.repo) is None


@pytest.mark.parametrize("user_native", [RuntimeError("no dialog")], indirect=True)
async def test_native_picker_failure_shows_input(user_native):
    await user_native.open("/")
    await user_native.should_not_see(marker="game-dir-input")
    user_native.find(marker="btn-choose-game-folder").click()
    await user_native.should_see(marker="game-dir-input")
    assert await _notified(user_native, "Folder picker unavailable")
    assert load_game_dir_setting(user_native.repo) is None


@pytest.mark.parametrize("user_native", [("C:/does/not/exist",)], indirect=True)
async def test_native_picker_invalid_choice_notifies(user_native):
    await user_native.open("/")
    user_native.find(marker="btn-choose-game-folder").click()
    await user_native.should_see("Kingdom Rush Genesis.exe")
    assert await _notified(user_native, "Game folder not found")
    assert load_game_dir_setting(user_native.repo) is None


async def test_native_picker_valid_choice_loads_editor(tmp_path, repo, game_paths):
    fake_window.install((str(game_paths.game_dir),))
    try:
        async with user_simulation(main_file=_error_page_main(tmp_path, repo, native=True)) as u:
            await u.open("/")
            u.find(marker="btn-choose-game-folder").click()
            await u.should_see("5857/5857 values placed", retries=50)
            assert load_game_dir_setting(repo) == game_paths.game_dir.resolve()
    finally:
        fake_window.uninstall()


async def test_topbar_switch_uses_new_folder(tmp_path, repo, game_paths, second_game):
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
    real_live_before = _live_file_state(game_paths.mods_dir)
    async with user_simulation(main_file=main_file) as u:
        await u.open("/")
        await u.should_see("5857/5857 values placed")
        u.find(marker="profile-menu").click()
        u.find("New").click()
        u.find(marker="profile-name").type("Keep")
        u.find("Create").click()
        u.find(marker="profile-menu").click()
        u.find(marker="profile-item-keep").click()

        # An invalid choice keeps the dialog open and the folder unchanged.
        empty = tmp_path / "empty"
        empty.mkdir()
        u.find(marker="game-folder").click()
        dialog = next(iter(u.find(marker="game-dialog").elements))
        assert dialog.value is True
        u.find(marker="game-dir-input").clear()
        u.find(marker="game-dir-input").type(str(empty))
        u.find(marker="btn-use-game-folder").click()
        assert await _notified(u, "Game file not found")
        assert dialog.value is True
        shown = next(iter(u.find(marker="game-dir-current").elements))
        assert shown.text == str(game_paths.game_dir)
        assert load_game_dir_setting(repo) == game_paths.game_dir
        # nicegui drops krmod.ui.main from sys.modules between simulations, so look it up now.
        ui_main = sys.modules["krmod.ui.main"]
        assert ui_main._active_state.paths.game_dir == game_paths.game_dir

        # A valid choice switches everything to the new folder.
        u.find(marker="game-dir-input").clear()
        u.find(marker="game-dir-input").type(str(second_game))
        u.find(marker="btn-use-game-folder").click()
        assert await _until(lambda: ui_main._active_state.paths.game_dir == second_game.resolve())
        paths = ui_main._active_state.paths
        assert paths.mods_dir == second_game.resolve() / "mods"
        assert paths.portraits_dir != game_paths.portraits_dir
        assert ui_main._active_state.profile.name == "Keep"
        assert load_game_dir_setting(repo) == second_game.resolve()

        # The reloaded page shows the editor and its dialog shows the new folder.
        async def dialog_shows_new_folder() -> bool:
            for _ in range(100):
                u.find(marker="game-folder").click()
                labels = u.find(marker="game-dir-current").elements
                if labels and next(iter(labels)).text == str(second_game.resolve()):
                    return True
                await asyncio.sleep(0.05)
            return False

        assert await dialog_shows_new_folder()
        await u.should_see("5857/5857 values placed", retries=50)

        # A live write lands in the new folder's mods dir, not in the real game's.
        u.find(marker="speed-2").click()
        live = second_game / "mods" / "kr_mod_live.lua"
        assert live.is_file()
        assert "2" in live.read_text(encoding="utf-8")
    assert _live_file_state(game_paths.mods_dir) == real_live_before
