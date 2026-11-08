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
# The game's spell room: a spell at level 3 with 1 point spent has 1 point left.
SPELL_ROOM = (
    "PowerRoomView = {}; "
    "function PowerRoomView:get_unit_stats(name) return { remaining_points = 3 - 1 - 1, level = 3 } end"
)


def _unlocked(harness, name):
    return harness.lua(f'return tostring(screen_map:is_content_stage_unlocked("{name}", {{}}))')


def _spell_points(harness):
    return harness.lua('return PowerRoomView:get_unit_stats("power_royal_edict").remaining_points')


def test_extra_points_are_added_to_every_level_and_never_stack(harness):
    harness.lua(BAL)
    harness.write_data([], rules={"extra_hero_points": 10, "extra_upgrade_points": 5})
    for _ in range(3):
        harness.run_level()
    assert harness.lua(TABLES) == "10,14,18|5,7,9"
    assert "points: hero skills +10, spell skills +0, skill tree +5" in harness.log()


def test_extra_spell_points_are_added_once_and_follow_the_rule(harness):
    harness.lua(BAL + "; " + SPELL_ROOM)
    harness.write_data([], rules={"extra_spell_points": 7})
    for _ in range(3):
        harness.run_level()
    assert _spell_points(harness) == "8"
    assert "spell skills +7" in harness.log()
    harness.write_data([], rules={"extra_spell_points": 0})
    harness.run_level()
    assert _spell_points(harness) == "1"


def test_extra_spell_points_before_the_spell_room_loads(harness):
    harness.lua(BAL + "; PowerRoomView = nil")
    harness.write_data([], rules={"extra_spell_points": 7})
    harness.run_level()
    log = harness.log()
    assert "spell points: waiting for the map screen" in log and "error" not in log


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


def test_unlock_spells_passes_spells_only(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_spells": True})
    harness.run_level()
    assert _unlocked(harness, "power_royal_edict") == "true"
    assert _unlocked(harness, "hero_ashbite") == "false"
    assert _unlocked(harness, "tower_wizard") == "false"
    assert "unlock spells: all" in harness.log() and "unlock heroes" not in harness.log()


def test_both_unlocks_keep_towers_locked(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_heroes": True, "unlock_spells": True})
    harness.run_level()
    assert _unlocked(harness, "hero_oni") == "true"
    assert _unlocked(harness, "power_musketeers") == "true"
    assert _unlocked(harness, "tower_sniper") == "false"


def test_unlock_towers_passes_tower_types_only(harness):
    harness.lua(BAL + "; " + MAP)
    harness.write_data([], rules={"unlock_towers": True})
    harness.run_level()
    assert _unlocked(harness, "tower_sniper") == "true"
    assert _unlocked(harness, "hero_oni") == "false"
    assert _unlocked(harness, "power_musketeers") == "false"
    assert "unlock towers: all" in harness.log()


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


# The game's skill tree: "a" was bought, so the other side of the split ("b", 3 points) and
# the far node "c" (9 points) are blocked; "d" is a normal node.
SKILL_TREE = (
    "KGraphDictionary = { graph = { tower_archers = { b = { cost = 3 }, c = { cost = 9 }, d = { cost = 1 } } } }; "
    "function KGraphDictionary:evaluate(source, points) "
    "  return { enable_buttons = { d = true }, available_nodes = { 'd' }, unavailable_buttons = {}, "
    "           block_buttons = { b = 'a', c = 'a' }, active_links = {} } end"
)
TREE_STATE = (
    "local r = KGraphDictionary:evaluate('tower_archers', 5); local function keys(t) "
    "local out = {} for k in pairs(t) do out[#out + 1] = k end table.sort(out) return table.concat(out, ',') end; "
    "table.sort(r.available_nodes); "
    "return keys(r.enable_buttons) .. '|' .. table.concat(r.available_nodes, ',') .. '|' .. "
    "keys(r.unavailable_buttons) .. '|' .. keys(r.block_buttons)"
)


def test_both_paths_turn_blocked_sides_into_buyable_nodes(harness):
    harness.lua(BAL + "; " + SKILL_TREE)
    harness.write_data([], rules={"allow_both_paths": True})
    for _ in range(3):
        harness.run_level()
    # b fits in 5 points, c does not; nothing is left to swap.
    assert harness.lua(TREE_STATE) == "b,d|b,d|c|"
    assert "unlock both skill paths: all trees" in harness.log()


def test_both_paths_off_keeps_the_game_split(harness):
    harness.lua(BAL + "; " + SKILL_TREE)
    harness.write_data([], rules={"allow_both_paths": True})
    harness.run_level()
    harness.write_data([], rules={"allow_both_paths": False})
    harness.run_level()
    assert harness.lua(TREE_STATE) == "d|d||b,c"
    assert "both skill paths" not in harness.log()
