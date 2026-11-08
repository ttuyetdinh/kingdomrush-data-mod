import pytest
from nicegui.testing.user_simulation import user_simulation

from krmod.app import load_state


async def test_shell_renders(user):
    await user.open("/")
    await user.should_see("KrGenesis Mod")
    for tab in ("Towers", "Troops", "Heroes", "Skills", "Enemies", "Items", "Stages", "Rules"):
        await user.should_see(tab)


async def test_card_opens_editor(user):
    await user.open("/")
    user.find("Archers").click()
    await user.should_see(marker="editor-title")


async def test_self_check_shown(user):
    await user.open("/")
    await user.should_see("5857/5857 values placed")


async def test_search_filters(user):
    await user.open("/")
    user.find(marker="card-search").type("knig")
    await user.should_see("Knights")
    await user.should_not_see("Archers")


async def test_new_profile(user):
    await user.open("/")
    user.find(marker="profile-menu").click()
    user.find("New").click()
    user.find(marker="profile-name").type("Hard")
    user.find("Create").click()
    await user.should_see("Hard")


@pytest.fixture
async def user_error(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    state, err = load_state(repo_dir=fake_repo)
    assert state is None
    assert err is not None
    assert "Kingdom Rush Genesis.exe" in err

    error_file = tmp_path / "ui_error_main.py"
    error_file.write_text(
        "from nicegui import core, ui\n"
        "from krmod.ui.main import build_page\n"
        "core.reset()\n"
        f"build_page(None, {repr(err)})\n"
        "ui.run()\n",
        encoding="utf-8",
    )
    async with user_simulation(main_file=error_file) as u:
        yield u


async def test_startup_error_page(user_error):
    await user_error.open("/")
    await user_error.should_see("Kingdom Rush Genesis.exe")


def test_load_state_missing_exe(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    fake_repo = tmp_path / "kingdomrush-data-mod"
    fake_repo.mkdir()
    state, err = load_state(repo_dir=fake_repo)
    assert state is None
    assert err is not None
    assert "Kingdom Rush Genesis.exe" in err


def test_load_state_non_zip_exe(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    game_dir = tmp_path / "game"
    repo_dir = game_dir / "kingdomrush-data-mod"
    game_dir.mkdir()
    repo_dir.mkdir()
    (game_dir / "Kingdom Rush Genesis.exe").write_text("not a valid zip", encoding="utf-8")
    (game_dir / "lua51.dll").write_bytes(b"dummy")
    state, err = load_state(repo_dir=repo_dir)
    assert state is None
    assert err is not None
    assert "Cannot read" in err


async def test_corrupt_profile_warning_shown(tmp_path):
    test_profiles = tmp_path / "test_profiles"
    test_profiles.mkdir()
    (test_profiles / "broken.json").write_text("{ corrupt json", encoding="utf-8")

    main_file = tmp_path / "corrupt_profile_main.py"
    main_file.write_text(
        "import dataclasses\n"
        "from pathlib import Path\n"
        "from nicegui import core, ui\n"
        "from krmod.gamedata.reader import read_balance\n"
        "from krmod.model.grouping import GroupIndex\n"
        "from krmod.paths import GamePaths\n"
        "from krmod.profiles import ProfileStore\n"
        "from krmod.state import AppState\n"
        "from krmod.ui.main import build_page\n"
        "core.reset()\n"
        "paths = GamePaths.locate()\n"
        f"paths = dataclasses.replace(paths, profiles_dir=Path({repr(str(test_profiles))}))\n"
        "tree = read_balance(paths)\n"
        "index = GroupIndex.build(tree)\n"
        "store = ProfileStore(paths.profiles_dir)\n"
        "state = AppState(paths, tree, index, store)\n"
        "build_page(state, None)\n"
        "ui.run()\n",
        encoding="utf-8",
    )
    async with user_simulation(main_file=main_file) as u:
        await u.open("/")
        await u.should_see("broken.json")

async def test_tab_switch_shows_tab_cards(user):
    await user.open("/")
    user.find("Enemies").click()
    await user.should_see("Demon lord")
    await user.should_not_see("Archers")


async def test_profile_duplicate_and_rename(user):
    await user.open("/")
    user.find(marker="profile-menu").click()
    user.find("Duplicate").click()
    user.find(marker="btn-duplicate").click()
    await user.should_see("Default (copy)")
    user.find(marker="profile-menu").click()
    await user.should_see(marker="profile-item-default-copy")


async def test_profile_error_shown_inline(user):
    await user.open("/")
    user.find(marker="profile-menu").click()
    user.find("New").click()
    # Attempt to create existing profile name "Default":
    user.find(marker="profile-name").type("Default")
    user.find("Create").click()
    # Should see the error inline and not crash:
    await user.should_see("already exists")

async def test_two_pages_render_independently(create_user):
    # NiceGUI builds one page per client. A click must update the page it came from,
    # not the page that was built last.
    first, second = create_user(), create_user()
    await first.open("/")
    await second.open("/")

    first.find("Archers").click()
    await first.should_see(marker="editor-title")
    await second.should_not_see(marker="editor-title")

    first.find("Enemies").click()
    await first.should_see("Demon lord")
    await second.should_see("Archers")
    await second.should_not_see("Demon lord")


async def test_page_built_line_printed(user, capsys):
    await user.open("/")
    assert " page built " in capsys.readouterr().out
