"""User simulation tests for Rules tab, live controls and apply bar (Task 13)."""
import sys
import pytest

from krmod.modgen import launcher
from krmod.modgen.launcher import RunningGame
from krmod.profiles import ProfileStore
from krmod.ui import applybar
@pytest.fixture
def state(user):
    sys.modules["krmod.ui.applybar"].POLL_INTERVAL_S = 0.05
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
    await user.should_see("started without the mod", retries=20)


async def test_unlock_switches_saved(user, state):
    await user.open("/")
    user.find("Rules").click()
    user.find("Unlock all tower levels").click()
    user.find("Unlock all heroes").click()
    saved = ProfileStore(state.paths.profiles_dir).active()
    assert (saved.unlock_tower_levels, saved.unlock_heroes) == (True, True)


async def test_extra_points_boxes_step_clamp_and_save(user, state):
    await user.open("/")
    user.find("Rules").click()
    _step(user, "extra-hero-points", 1, shift=True)
    _step(user, "extra-hero-points", 1)
    assert state.profile.extra_hero_points == 11
    _step(user, "extra-hero-points", -1, shift=True)
    _step(user, "extra-hero-points", -1, shift=True)
    assert _box_text(user, "extra-hero-points") == "0"
    _commit(user, "extra-upgrade-points", "12.5")
    assert state.profile.extra_upgrade_points == 13
    _commit(user, "extra-upgrade-points", "5000")
    assert _box_text(user, "extra-upgrade-points") == "999"
    _commit(user, "extra-upgrade-points", "abc")
    await user.should_see("Not a number")
    assert _box_text(user, "extra-upgrade-points") == "999"
    assert ProfileStore(state.paths.profiles_dir).active().extra_upgrade_points == 999

async def test_speed_button_markers_and_highlight(user, state):
    await user.open("/")
    user.find(marker="speed-3").click()
    assert state.profile.live.speed == 3
    live_file = state.paths.mods_dir / "kr_mod_live.lua"
    assert "speed = 3" in live_file.read_text()


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
    await user.should_see("Waiting for the game to load the mod", retries=20)

    # Test UPDATED_RUNNING
    monkeypatch.setattr(launcher, "find_game", lambda paths: RunningGame(2, True))
    await user.open("/")
    user.find(marker="apply-run").click()
    await user.should_see("Game is running: changes apply at the next level start", retries=20)


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


def _box_text(user, marker):
    return list(user.find(marker=marker).elements)[0].value


def _step(user, marker, direction, shift=False):
    user.find(marker=marker).trigger("step", {"direction": direction, "shiftKey": shift})


def _commit(user, marker, text):
    user.find(marker=marker).clear().type(text).trigger("commit")


async def test_live_boxes_on_rules_tab_step(user, state):
    await user.open("/")
    user.find("Rules").click()
    live_file = state.paths.mods_dir / "kr_mod_live.lua"
    assert _box_text(user, "rules-enemy-mult") == "1"
    assert _box_text(user, "rules-troop-delta") == "0"

    _step(user, "rules-enemy-mult", -1)
    assert state.profile.live.enemy_mult == 0.25
    assert _box_text(user, "rules-enemy-mult") == "0.25"
    _step(user, "rules-enemy-mult", 1)
    assert state.profile.live.enemy_mult == 1.0
    _step(user, "rules-enemy-mult", 1)
    assert state.profile.live.enemy_mult == 2.0

    _step(user, "rules-troop-delta", 1)
    _step(user, "rules-troop-delta", 1)
    assert state.profile.live.troop_delta == 2
    assert _box_text(user, "rules-troop-delta") == "+2"
    _step(user, "rules-troop-delta", -1)
    _step(user, "rules-troop-delta", -1)
    _step(user, "rules-troop-delta", -1)
    assert state.profile.live.troop_delta == -1
    assert _box_text(user, "rules-troop-delta") == "-1"
    assert "troop_delta = -1" in live_file.read_text()
    assert "enemy_mult = 2.0" in live_file.read_text()


async def test_live_boxes_typed_values_snap_clamp_and_reject(user, state):
    await user.open("/")
    user.find("Rules").click()

    _commit(user, "rules-enemy-mult", "5")
    assert state.profile.live.enemy_mult == 5.0
    _commit(user, "rules-enemy-mult", "0.3")
    assert state.profile.live.enemy_mult == 0.25
    assert _box_text(user, "rules-enemy-mult") == "0.25"
    _commit(user, "rules-enemy-mult", "99")
    assert state.profile.live.enemy_mult == 10.0

    _commit(user, "rules-troop-delta", "-3.4")
    assert state.profile.live.troop_delta == -3
    assert _box_text(user, "rules-troop-delta") == "-3"
    _commit(user, "rules-troop-delta", "+50")
    assert state.profile.live.troop_delta == 10
    assert _box_text(user, "rules-troop-delta") == "+10"

    # rejected text: the saved value stays and the box reverts
    _commit(user, "rules-troop-delta", "abc")
    await user.should_see("Not a number")
    assert state.profile.live.troop_delta == 10
    assert _box_text(user, "rules-troop-delta") == "+10"
    user.find(marker="rules-enemy-mult").clear().trigger("commit")
    await user.should_see("Value cannot be empty")
    assert state.profile.live.enemy_mult == 10.0
    assert _box_text(user, "rules-enemy-mult") == "10"


async def test_topbar_and_rules_live_boxes_stay_in_sync(user, state):
    await user.open("/")
    _step(user, "enemy-mult", 1)
    assert state.profile.live.enemy_mult == 2.0
    _commit(user, "troop-delta", "-2")
    assert state.profile.live.troop_delta == -2

    user.find("Rules").click()
    assert _box_text(user, "rules-enemy-mult") == "2"
    assert _box_text(user, "rules-troop-delta") == "-2"
    _step(user, "rules-troop-delta", 1)
    assert _box_text(user, "troop-delta") == "-1"



async def test_rules_tab_explains_live_controls(user):
    await user.open("/")
    user.find("Rules").click()
    await user.should_see("Bosses always spawn once")
    await user.should_see("A large minus can leave a barracks empty")


async def test_log_summary_panel_display(user, state, monkeypatch):
    import os, time
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
    import asyncio
    await asyncio.sleep(0.4)
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

    await asyncio.sleep(0.4)
    await user.should_see(marker="log-summary-panel")
    await user.should_see("Game is running: changes apply at the next level start")
    await user.should_not_see("Applied: 10 changes")

async def test_reset_all_rerenders_open_card(user):
    await user.open("/")
    user.find("Archers").click()
    cell = user.find(marker="cell-towers.archers.price.1")
    cell.clear().type("7").trigger("commit")
    c = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    assert c.props.get("original") == "70"

    user.find(marker="reset-all").click()
    user.find(marker="btn-confirm-reset").click()

    c = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    assert c.props.get("original") is None
    assert c.props.get("tone") is None
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
    await user.should_see("Mod written: changes apply at the next level start")

    log_content = "applied 8 changes\n"
    log_file.write_text(log_content, encoding="utf-8")
    future_time = time.time() + 5
    os.utime(log_file, (future_time, future_time))

    await asyncio.sleep(0.4)
    await user.should_see(marker="log-summary-panel")
    await user.should_see("Game is running: changes apply at the next level start")
    await user.should_not_see("Applied: 8 changes")

async def test_log_written_before_apply_produces_no_panel(user, state, monkeypatch):
    import os, time, asyncio
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)
    await user.open("/")

    log_file = state.paths.mods_dir / "kr_mod_log.txt"
    log_file.write_text("applied 2 changes\n", encoding="utf-8")
    past_time = time.time() - 10
    os.utime(log_file, (past_time, past_time))

    user.find(marker="apply-mod").click()
    await asyncio.sleep(0.4)
    await user.should_not_see(marker="log-summary-panel")

async def test_polling_timeout_hides_status_line(user, monkeypatch):
    import asyncio
    await user.open("/")
    monkeypatch.setattr(launcher, "find_game", lambda paths: None)
    monkeypatch.setattr(sys.modules["krmod.ui.applybar"], "POLL_INTERVAL_S", 0.02)

    user.find(marker="apply-run").click()
    # The handler finishes off the event loop; the status line shows once it is done.
    await user.should_see(marker="status-line")
    status_el = list(user.find(marker="status-line").elements)[0]
    assert status_el.visible is True

    monkeypatch.setattr(sys.modules["krmod.ui.applybar"], "POLL_TIMEOUT_S", 0.05)
    await asyncio.sleep(0.2)
    assert status_el.visible is False


async def test_apply_scans_processes_off_the_event_loop(user, monkeypatch):
    import threading

    loop_thread = threading.get_ident()
    seen = []

    def fake_find_game(paths):
        seen.append(threading.get_ident())
        return None

    monkeypatch.setattr(launcher, "find_game", fake_find_game)
    await user.open("/")
    user.find(marker="apply-mod").click()
    await user.should_see("Mod written:")
    user.find(marker="apply-run").click()
    await user.should_see("Waiting for the game to load the mod", retries=20)
    assert seen
    assert loop_thread not in seen


async def test_double_click_apply_and_run_launches_once(user, monkeypatch):
    import asyncio
    import time

    launches = []

    def slow_find_game(paths):
        time.sleep(0.3)  # the real process scan takes a moment
        return None

    monkeypatch.setattr(launcher, "find_game", slow_find_game)
    monkeypatch.setattr(launcher, "launch", lambda paths: launches.append(1) or 99999)
    await user.open("/")
    run_button = list(user.find(marker="apply-run").elements)[0]
    apply_button = list(user.find(marker="apply-mod").elements)[0]
    user.find(marker="apply-run").click()
    await asyncio.sleep(0.05)
    assert not run_button.enabled and not apply_button.enabled
    # A real window can deliver a second click before it shows the disabled state.
    run_button.enable()
    apply_button.enable()
    user.find(marker="apply-run").click()
    user.find(marker="apply-mod").click()
    await user.should_see("Waiting for the game to load the mod", retries=20)
    await asyncio.sleep(0.5)
    assert launches == [1]
    assert run_button.enabled and apply_button.enabled
