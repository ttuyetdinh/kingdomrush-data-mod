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
        "return { speed = 5, enemy_mult = 1, troop_mult = 1 }",
    )
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return game.DBG_TIME_MULT") == "2"
    harness.write_raw(
        "kr_mod_live.lua",
        "return { speed = 1, enemy_mult = 0.6, troop_mult = 1 }",
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


def test_read_live_validation(harness):
    setup(harness)
    check = """
    local live_mod = dofile(GAME_DIR .. "/mods/kr_mod/live.lua")
    local path = GAME_DIR .. "/mods/kr_mod_live.lua"
    return tostring(live_mod.read_live(path) ~= nil)
    """
    assert harness.lua(check) == "true"

    # bad speed
    harness.write_raw("kr_mod_live.lua", "return { speed = 0, enemy_mult = 1, troop_mult = 1 }")
    assert harness.lua(check) == "false"
    # bad enemy mult
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 0.4, troop_mult = 1 }")
    assert harness.lua(check) == "false"
    # bad troop mult
    harness.write_raw("kr_mod_live.lua", "return { speed = 1, enemy_mult = 1, troop_mult = 3.25 }")
    assert harness.lua(check) == "false"
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
    harness.write_raw("kr_mod_live.lua", "return { speed = 99, enemy_mult = 1, troop_mult = 1 }")
    harness.lua("NOW = 1; game:update(0.03)")
    assert harness.lua("return tostring(POLLER_COUNT)") == "1"
