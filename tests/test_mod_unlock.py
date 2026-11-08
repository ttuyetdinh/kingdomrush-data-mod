BAL = "BAL = { towers = { archers = { price = { 70, 110 } } } }"


def test_unlock_strips_level_locks_only(harness):
    harness.lua(
        BAL + '; game.store.level = { locked_towers = { "tower_build_archers", "archers_lvl2", "knights_lvl4" } }'
    )
    harness.write_data([], unlock=True)
    harness.run_level()
    assert harness.lua("return table.concat(game.store.level.locked_towers, ',')") == "tower_build_archers"
    assert "unlock" in harness.log() and "removed 2, kept 1" in harness.log()


def test_unlock_off_leaves_locks(harness):
    harness.lua(BAL + '; game.store.level = { locked_towers = { "archers_lvl2" } }')
    harness.write_data([], unlock=False)
    harness.run_level()
    assert harness.lua("return #game.store.level.locked_towers") == "1"
    assert "unlock" not in harness.log()


def test_unlock_strips_level_data_too(harness):
    harness.lua(
        BAL + '; game.store.level = { data = { locked_towers = { "a_lvl2", "tower_build_x", "b_lvl3" } } }'
    )
    harness.write_data([], unlock=True)
    harness.run_level()
    assert harness.lua("return table.concat(game.store.level.data.locked_towers, ',')") == "tower_build_x"


def test_strip_keeps_order_and_non_strings(harness):
    harness.lua(BAL)
    harness.write_data([])
    harness.run_level()
    out = harness.lua(
        """local U = dofile(KRMOD.base .. "/mods/kr_mod/unlock.lua")
        local list = { "x", "a_lvl2", 5, "b_lvl10", "lvl2x", "y_lvl3" }
        local removed, kept = U.strip(list)
        return removed .. "," .. kept .. ":" .. table.concat(list, ",")"""
    )
    assert out == "3,3:x,5,lvl2x"


def test_load_data_wrapped_once_and_respects_flag(harness):
    harness.lua(BAL + '; LEVEL_DATA = { locked_towers = { "archers_lvl2" } }')
    harness.write_data([], unlock=True)
    for _ in range(3):
        harness.run_level()
    assert harness.lua('return #require("level_utils").load_data({}).locked_towers') == "0"
    harness.lua('LEVEL_DATA = { locked_towers = { "archers_lvl2" } }')
    harness.write_data([], unlock=False)
    harness.run_level()
    assert harness.lua('return #require("level_utils").load_data({}).locked_towers') == "1"


def test_load_data_wrapper_passes_through_nil_and_extra_returns(harness):
    harness.lua(BAL + "; LEVEL_DATA = nil")
    harness.write_data([], unlock=True)
    harness.run_level()
    assert harness.lua('return tostring(require("level_utils").load_data({}))') == "nil"
