BAL = "BAL = { towers = { archers = { price = { 70, 110 } } } }"
TABLES = (
    'local GS = require("game_settings"); '
    "return table.concat(GS.skill_points_for_hero_level, ',') .. '|' .. "
    "table.concat(GS.upgrades_points_per_stage, ',')"
)
# The game's star check: nothing is unlocked; CALLS counts how often it runs.
MAP = (
    "CALLS = 0; screen_map = {}; "
    "function screen_map:is_content_stage_unlocked(name, ud) CALLS = CALLS + 1; return false end"
)


def _unlocked(harness, name):
    return harness.lua(f'return tostring(screen_map:is_content_stage_unlocked("{name}", {{}}))')


def test_extra_points_are_added_to_every_level_and_never_stack(harness):
    harness.lua(BAL)
    harness.write_data([], rules={"extra_hero_points": 10, "extra_upgrade_points": 5})
    for _ in range(3):
        harness.run_level()
    assert harness.lua(TABLES) == "10,14,18|5,7,9"
    assert "points: hero skills +10, skill tree +5" in harness.log()


def test_zero_extra_points_restore_the_game_numbers(harness):
    harness.lua(BAL)
    harness.write_data([], rules={"extra_hero_points": 10, "extra_upgrade_points": 5})
    harness.run_level()
    harness.write_data([], rules={"extra_hero_points": 0, "extra_upgrade_points": 0})
    harness.run_level()
    assert harness.lua(TABLES) == "0,4,8|0,2,4"
    assert "points" not in harness.log()


def test_unlock_heroes_passes_heroes_only(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_heroes": True})
    harness.run_level()
    assert _unlocked(harness, "hero_ashbite") == "true"
    assert _unlocked(harness, "tower_wizard") == "false"
    assert _unlocked(harness, "power_royal_edict") == "false"
    assert "unlock heroes: all" in harness.log()


def test_unlock_heroes_off_keeps_star_locks_and_wraps_once(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_heroes": True})
    for _ in range(3):
        harness.run_level()
    harness.write_data([], rules={"unlock_heroes": False})
    harness.run_level()
    harness.lua("CALLS = 0")
    assert _unlocked(harness, "hero_ashbite") == "false"
    assert harness.lua("return CALLS") == "1"
    assert "unlock heroes" not in harness.log()


def test_reloaded_map_screen_is_wrapped_again(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_heroes": True})
    harness.run_level()
    harness.lua(MAP)
    harness.run_level()
    assert _unlocked(harness, "hero_oni") == "true"


def test_unlock_heroes_before_the_map_screen_loads(harness):
    harness.lua(BAL + "; screen_map = nil")
    harness.write_data([], rules={"unlock_heroes": True})
    harness.run_level()
    log = harness.log()
    assert "unlock heroes: waiting for the map screen" in log and "error" not in log
