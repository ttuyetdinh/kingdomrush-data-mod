import pytest

def setup(h, speed=1):
    h.lua("BAL = { towers = {} }")
    h.write_data([])
    h.write_live(speed=speed)
    h.run_level()


def test_start_speed_from_live_file(harness):
    setup(harness, speed=2)
    assert harness.lua("return game.DBG_TIME_MULT") == "2"


def test_speed_keys_consumed(harness):
    setup(harness)
    assert harness.lua('return tostring(game:keypressed("f7"))') == "true"
    assert harness.lua("return game.DBG_TIME_MULT") == "3"
    assert harness.lua("return tostring(LAST_KEY)") == "nil"
    harness.lua('game:keypressed("a")')
    assert harness.lua("return LAST_KEY") == "a"


def test_poll_applies_file_change_but_not_unchanged_file(harness):
    setup(harness)
    harness.lua('game:keypressed("f6")')
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    harness.write_live(speed=3)
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "3"


def test_invalid_live_ignored(harness):
    setup(harness, speed=2)
    harness.write_raw(
        "kr_mod_live.lua",
        "return { speed = 5, enemy_mult = 1, troop_delta = 0 }",
    )
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    harness.write_raw(
        "kr_mod_live.lua",
        "return { speed = 1, enemy_mult = 0.6, troop_delta = 0 }",
    )
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"


def test_hooks_installed_once(harness):
    setup(harness)
    harness.run_level()
    harness.run_level()
    harness.lua("game:update(0.03)")
    assert harness.lua("return GAME_UPDATES") == "1"


def test_badge(harness):
    setup(harness, speed=1)
    harness.lua("game:draw()")
    assert harness.lua("return #PRINTS") == "0"
    harness.lua('game:keypressed("f6"); game:draw()')
    assert harness.lua("return PRINTS[1]") == "x2"
    assert harness.lua("return tostring(LAST_PRINT_X)") == "940"
    assert harness.lua("return tostring(LAST_PRINT_Y)") == "12"


def test_read_live_validation(harness):
    setup(harness)
    check = """
    local live_mod = dofile(GAME_DIR .. "/mods/kr_mod/live.lua")
    local path = GAME_DIR .. "/mods/kr_mod_live.lua"
    return tostring(live_mod.read_live(path) ~= nil)
    """
    assert harness.lua(check) == "true"

    # bad speed
    harness.write_raw("kr_mod_live.lua", "return { speed = 0, enemy_mult = 1, troop_delta = 0 }")
    assert harness.lua(check) == "false"
    # enemy mult outside the allowed list
    for bad in ("0.4", "0.5", "1.5", "101", "0", "-1"):
        harness.write_raw("kr_mod_live.lua", f"return {{ speed = 1, enemy_mult = {bad}, troop_delta = 0 }}")
        assert harness.lua(check) == "false", bad
    # troop delta not a whole number in -10..100
    for bad in ("1.5", "101", "-11", "'2'"):
        harness.write_raw("kr_mod_live.lua", f"return {{ speed = 1, enemy_mult = 1, troop_delta = {bad} }}")
        assert harness.lua(check) == "false", bad
    # group gap not a whole number in 10..500 (a file without one means 100)
    for bad in ("9", "501", "50.5", "'50'"):
        harness.write_raw(
            "kr_mod_live.lua", f"return {{ speed = 1, enemy_mult = 1, troop_delta = 0, group_gap = {bad} }}"
        )
        assert harness.lua(check) == "false", bad
    # the old troop_mult field alone is not enough
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 1, troop_mult = 1 }")
    assert harness.lua(check) == "false"
    # every allowed value passes
    for enemy in ("0.25", "1", "2", "10", "10.0000001", "30", "100"):
        for troop in ("-10", "0", "7", "10", "100"):
            harness.write_raw(
                "kr_mod_live.lua", f"return {{ speed = 1, enemy_mult = {enemy}, troop_delta = {troop} }}"
            )
            assert harness.lua(check) == "true", (enemy, troop)
    # missing file
    assert harness.lua("""
    local live_mod = dofile(GAME_DIR .. "/mods/kr_mod/live.lua")
    return tostring(live_mod.read_live(GAME_DIR .. "/mods/nonexistent.lua") ~= nil)
    """) == "false"


def test_pollers_called_and_errors_contained(harness):
    setup(harness)
    harness.lua("""
    POLLER_CALLED = 0
    KRMOD.pollers["test_poller"] = function(K)
      POLLER_CALLED = POLLER_CALLED + 1
    end
    KRMOD.pollers["bad_poller"] = function(K)
      error("poller failure")
    end
    """)
    harness.write_live(speed=2)
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return tostring(POLLER_CALLED)") == "1"
    assert "error poller bad_poller" in harness.log()


def test_enemy_mult_logged_when_changed(harness):
    setup(harness)
    harness.write_live(enemy_mult=2.0)
    harness.lua("NOW = 1; game:update(0.03)")
    assert "enemies x2" in harness.log()
    # unchanged enemy_mult does not log again
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.log().count("enemies x2") == 1


def test_badge_clears_on_speed_1(harness):
    setup(harness, speed=2)
    harness.lua("game:draw()")
    assert harness.lua("return #PRINTS") == "1" and harness.lua("return PRINTS[1]") == "x2"
    harness.lua('game:keypressed("f5")')
    harness.lua("game:draw()")
    assert harness.lua("return #PRINTS") == "1"


def test_custom_speed_keys(harness):
    harness.lua("BAL = { towers = {} }")
    harness.write_data(speed_keys=("1", "2", "3"))
    harness.write_live(speed=1)
    harness.run_level()
    harness.lua('game:keypressed("2")')
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    assert "speed x2" in harness.log()


def test_install_without_game_is_safe(harness):
    harness.lua("OLD_GAME = game; game = nil")
    try:
        harness.lua("""
        local live_mod = dofile(GAME_DIR .. "/mods/kr_mod/live.lua")
        live_mod.install({ installed = {} }, { base = GAME_DIR, log = function() end })
        """)
    finally:
        harness.lua("game = OLD_GAME")


def test_badge_color_channels(harness):
    setup(harness, speed=2)
    harness.lua("""
    COLORS_CALLED = {}
    love.graphics.setColor = function(...)
      table.insert(COLORS_CALLED, table.concat({...}, ","))
    end
    game:draw()
    """)
    assert harness.lua("return COLORS_CALLED[1]") == "255,255,255,255"


def test_original_update_error_propagates(harness):
    harness.lua('game.update = function() error("game crashed") end')
    setup(harness)
    with pytest.raises(Exception, match="game crashed"):
        harness.lua("game:update(0.03)")


def test_pollers_called_when_live_file_invalid(harness):
    setup(harness)
    harness.lua("""
    POLLER_COUNT = 0
    KRMOD.pollers["always_poll"] = function(K)
      POLLER_COUNT = POLLER_COUNT + 1
    end
    """)
    harness.write_raw("kr_mod_live.lua", "return { speed = 99, enemy_mult = 1, troop_delta = 0 }")
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return tostring(POLLER_COUNT)") == "1"


def test_badge_centered_without_getfont(harness):
    setup(harness, speed=2)
    harness.lua("love.graphics.getFont = nil; game:draw()")
    assert harness.lua("return tostring(LAST_PRINT_X)") == "940"


def test_speed_click_reapplies_same_speed_after_key(harness):
    setup(harness)
    harness.write_live(speed=1, seq=10)
    harness.lua("NOW = 1; game:update(0.03)")
    harness.lua('game:keypressed("f6")')
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    # other writes keep the same seq: the key press stays in force
    harness.write_live(speed=1, enemy_mult=2.0, seq=10)
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    # a click on the already highlighted x1 bumps seq and wins over the key press
    harness.write_live(speed=1, enemy_mult=2.0, seq=11)
    harness.lua("NOW = 3; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "1"
    assert harness.lua("return KRMOD.live.speed") == "1"
    assert "speed x1" in harness.log()


def test_file_without_seq_keeps_old_rule(harness):
    setup(harness)
    harness.lua('game:keypressed("f6")')
    harness.write_live(speed=1)
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"


def test_troop_delta_and_enemy_mult_copied_into_live(harness):
    setup(harness)
    assert harness.lua("return KRMOD.live.troop_delta") == "0"
    harness.write_live(enemy_mult=0.25, troop_delta=-3)
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return KRMOD.live.troop_delta") == "-3"
    assert harness.lua("return KRMOD.live.enemy_mult") == "0.25"
    # an invalid file leaves the last good values in force
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 101, troop_delta = 5 }")
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.lua("return KRMOD.live.troop_delta") == "-3"
    assert harness.lua("return KRMOD.live.enemy_mult") == "0.25"


def test_group_gap_copied_into_live(harness):
    setup(harness)
    assert harness.lua("return KRMOD.live.group_gap") == "100"
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 1, troop_delta = 0, group_gap = 50 }")
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return KRMOD.live.group_gap") == "50"
    assert "group gaps 50%" in harness.log()
    # a live file from before the Gaps box: the game's own gaps
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 1, troop_delta = 0 }")
    harness.lua("NOW = 2; game:update(0.03)")
    assert harness.lua("return KRMOD.live.group_gap") == "100"
