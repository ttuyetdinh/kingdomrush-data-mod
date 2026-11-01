import pytest
from nicegui.testing.user_simulation import user_simulation

from krmod.ui import main as ui_main


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
async def user_error(tmp_path):
    error_file = tmp_path / "ui_error_main.py"
    error_file.write_text(
        "from nicegui import core, ui\n"
        "from krmod.ui.main import build_page\n"
        "core.reset()\n"
        'build_page(None, "Game file not found: Kingdom Rush Genesis.exe")\n'
        "ui.run()\n",
        encoding="utf-8",
    )
    async with user_simulation(main_file=error_file) as u:
        yield u


async def test_startup_error_page(user_error):
    await user_error.open("/")
    await user_error.should_see("Kingdom Rush Genesis.exe")


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


async def test_profile_error_shown_inline(user):
    await user.open("/")
    user.find(marker="profile-menu").click()
    user.find("New").click()
    # Attempt to create existing profile name "Default":
    user.find(marker="profile-name").type("Default")
    user.find("Create").click()
    # Should see the error inline and not crash:
    await user.should_see("already exists")


async def test_regions_exposed(user):
    await user.open("/")
    assert isinstance(ui_main.REGIONS, dict)
    for key in ("left", "right", "bottom", "topbar_right"):
        assert key in ui_main.REGIONS
    assert callable(ui_main.show_card)
    assert callable(ui_main.refresh)
