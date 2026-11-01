"""User simulation tests for Rules tab, live controls and apply bar (Task 13)."""
import sys
import pytest

from krmod.modgen import launcher
from krmod.modgen.launcher import RunningGame
from krmod.profiles import ProfileStore

@pytest.fixture
def state(user):
    return sys.modules["krmod.ui.main"]._active_state

@pytest.fixture(autouse=True)
def safe_launcher(monkeypatch):
    monkeypatch.setattr(launcher, "launch", lambda paths: 99999)
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)


async def test_speed_button_writes_live(user, state):
    await user.open("/")
    user.find("×2").click()
    live_file = state.paths.mods_dir / "kr_mod_live.lua"
    assert live_file.is_file()
    assert "speed = 2" in live_file.read_text()


async def test_forbidden_key_rejected(user):
    await user.open("/")
    user.find("Rules").click()
    user.find(marker="speed-key-1").clear().type("space").trigger("blur")
    await user.should_see("can't be used")


async def test_apply_running_unmodded(user, monkeypatch):
    monkeypatch.setattr(launcher, "find_game", lambda paths: RunningGame(1, False))
    await user.open("/")
    user.find("Apply mod and run game").click()
    await user.should_see("started without the mod")


async def test_unlock_switch_saved(user, state):
    await user.open("/")
    user.find("Rules").click()
    user.find("Unlock all tower levels").click()
    assert ProfileStore(state.paths.profiles_dir).active().unlock_tower_levels is True

async def test_speed_button_markers_and_highlight(user, state):
    await user.open("/")
    user.find(marker="speed-3").click()
    assert state.profile.live.speed == 3
    live_file = state.paths.mods_dir / "kr_mod_live.lua"
    assert "speed = 3" in live_file.read_text()


async def test_enemy_mult_slider_topbar(user, state):
    await user.open("/")
    user.find(marker="enemy-mult").trigger("change", 1.5)
    assert state.profile.live.enemy_mult == 1.5
    await user.should_see("Enemies 1.5x")


async def test_troop_mult_slider_topbar(user, state):
    await user.open("/")
    user.find(marker="troop-mult").trigger("change", 2.25)
    assert state.profile.live.troop_mult == 2.25
    await user.should_see("Troops 2.25x")


async def test_speed_keys_valid_save(user, state):
    await user.open("/")
    user.find("Rules").click()
    user.find(marker="speed-key-1").clear().type("f8").trigger("blur")
    assert state.profile.speed_keys[0] == "f8"


async def test_reset_all_dialog(user, state):
    await user.open("/")
    # Set a dummy change in active profile
    dummy_path = ("towers", "archers", "price", 1)
    state.set_value(dummy_path, 10.0)
    assert len(state.profile.changes) > 0

    # Click reset all
    user.find(marker="reset-all").click()
    await user.should_see("Reset all changes?")

    # Click confirm
    user.find(marker="btn-confirm-reset").click()
    assert len(state.profile.changes) == 0


async def test_apply_mod_notification(user, state):
    await user.open("/")
    user.find(marker="apply-mod").click()
    await user.should_see("Mod written:")


async def test_stale_changes_displayed_when_present(user, state):
    await user.open("/")
    user.find("Rules").click()
    await user.should_not_see(marker="stale-list")

    # Inject stale change
    stale_path = ("towers", "archers", "price", 999)
    state.profile.changes[stale_path] = 42.0
    state.store.save(state.profile)

    user.find("Towers").click()
    user.find("Rules").click()
    await user.should_see(marker="stale-list")
    await user.should_see("towers.archers.price.999")


async def test_apply_and_run_outcomes(user, monkeypatch):
    # Test LAUNCHED
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)
    await user.open("/")
    user.find(marker="apply-run").click()
    await user.should_see("Waiting for the game to load the mod")

    # Test UPDATED_RUNNING
    monkeypatch.setattr(launcher, "find_game", lambda paths: RunningGame(2, True))
    await user.open("/")
    user.find(marker="apply-run").click()
    await user.should_see("Game is running: changes apply at the next level start")


async def test_profile_menu_slug_marker(user):
    await user.open("/")
    user.find(marker="profile-menu").click()
    await user.should_see(marker="profile-item-default")


async def test_speed_keys_enter_key_and_errors(user, state):
    await user.open("/")
    user.find("Rules").click()

    # Invalid LOVE key name via enter
    user.find(marker="speed-key-2").clear().type("invalid_key").trigger("keydown.enter")
    await user.should_see("not a LOVE key name")
    assert state.profile.speed_keys[1] == "f6"

    # Duplicate key
    user.find(marker="speed-key-1").clear().type("f6").trigger("keydown.enter")
    await user.should_see("3 distinct keys")
    assert state.profile.speed_keys[0] == "f5"


async def test_mirrored_multipliers_on_rules_tab(user, state):
    await user.open("/")
    user.find("Rules").click()

    # Mirrored enemy slider
    user.find(marker="rules-enemy-mult").trigger("change", 2.5)
    assert state.profile.live.enemy_mult == 2.5
    await user.should_see("Enemies 2.5x")

    # Mirrored troop slider
    user.find(marker="rules-troop-mult").trigger("change", 0.75)
    assert state.profile.live.troop_mult == 0.75
    await user.should_see("Troops 0.75x")


async def test_log_summary_panel_display(user, state, monkeypatch):
    import os, time, asyncio
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)

    await user.open("/")
    log_file = state.paths.mods_dir / "kr_mod_log.txt"

    # Click apply mod
    user.find(marker="apply-mod").click()

    # Write log with summary
    log_content = (
        "applied 4 changes\n"
        "missing towers.archers.unknown_stat\n"
        "unlock classic: removed 1, kept 2\n"
        "error syntax error in custom file\n"
    )
    log_file.write_text(log_content, encoding="utf-8")
    future_time = time.time() + 5
    os.utime(log_file, (future_time, future_time))

    # Wait for timer poll tick
    await asyncio.sleep(1.2)
    await user.should_see("Applied: 4 changes")
    await user.should_see("towers.archers.unknown_stat")
    await user.should_see("syntax error in custom file")
    await user.should_see("classic: removed 1, kept 2")


async def test_log_summary_panel_updated_running(user, state, monkeypatch):
    import os, time, asyncio
    monkeypatch.setattr(launcher, "find_game", lambda paths: RunningGame(2, True))

    await user.open("/")
    log_file = state.paths.mods_dir / "kr_mod_log.txt"

    # Click apply and run
    user.find(marker="apply-run").click()

    log_content = "applied 10 changes\n"
    log_file.write_text(log_content, encoding="utf-8")
    future_time = time.time() + 5
    os.utime(log_file, (future_time, future_time))

    await asyncio.sleep(1.2)
    await user.should_not_see("Applied: 10 changes")
    await user.should_see("Game is running: changes apply at the next level start")


async def test_reset_all_rerenders_open_card(user):
    await user.open("/")
    user.find("Archers").click()
    cell = user.find(marker="cell-towers.archers.price.1")
    cell.clear().type("7").trigger("keydown.enter")
    await user.should_see(marker="orig-towers.archers.price.1")

    user.find(marker="reset-all").click()
    user.find(marker="btn-confirm-reset").click()

    await user.should_not_see(marker="orig-towers.archers.price.1")
    c = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    assert c.value == "70"


async def test_profile_switch_on_rules_tab_preserves_rules_view(user):
    await user.open("/")
    user.find("Archers").click()
    await user.should_see(marker="editor-title")

    user.find("Rules").click()
    await user.should_see("Progression Rules")

    user.find(marker="profile-menu").click()
    user.find("New").click()
    user.find(marker="profile-name").type("Alt")
    user.find("Create").click()

    await user.should_see("Progression Rules")
    await user.should_not_see(marker="editor-title")


async def test_apply_mod_with_running_modded_game(user, state, monkeypatch):
    import os, time, asyncio
    monkeypatch.setattr(launcher, "find_game", lambda paths: RunningGame(1, True))
    await user.open("/")

    log_file = state.paths.mods_dir / "kr_mod_log.txt"
    user.find(marker="apply-mod").click()

    log_content = "applied 8 changes\n"
    log_file.write_text(log_content, encoding="utf-8")
    future_time = time.time() + 5
    os.utime(log_file, (future_time, future_time))

    await asyncio.sleep(1.2)
    await user.should_not_see("Applied: 8 changes")
    await user.should_see("Game is running: changes apply at the next level start")


async def test_log_written_before_apply_produces_no_panel(user, state, monkeypatch):
    import asyncio
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)
    await user.open("/")

    log_file = state.paths.mods_dir / "kr_mod_log.txt"
    log_file.write_text("applied 2 changes\n", encoding="utf-8")

    user.find(marker="apply-mod").click()
    await asyncio.sleep(1.2)

    await user.should_not_see(marker="log-summary-panel")
