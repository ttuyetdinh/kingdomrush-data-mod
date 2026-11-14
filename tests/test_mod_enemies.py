import pytest


def spawn(h, enemies, mult, gems_idx=(), wait=1.0, reset_acc=True, pi=1, spi="1"):
    acc_reset = "KRMOD.enemy_acc = {};" if reset_acc else ""
    entries = ",".join(f'{{pi={pi},spi={spi},enemy="{e}"}}' for e in enemies)
    return h.lua(
        f"""KRMOD.live.enemy_mult = {mult}; {acc_reset} SPAWN_CALLS = {{}}; WAITS = {{}}
      local store = {{ current_spawn_idx = 0, gems_spawn_idx = {{ {",".join(map(str, gems_idx))} }}, gems_per_wave = 10 }}
      local cmd = {{ wait_time = {wait}, spawns = {{ {entries} }} }}
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      LAST_STORE = store; LAST_CMD = cmd; return #SPAWN_CALLS"""
    )


def lanes_and_rows(h):
    """Each spawn as "<lane>@<number of waits before it>", in spawn order."""
    return h.lua(
        "local t = {}; for _, c in ipairs(SPAWN_CALLS) do t[#t + 1] = tostring(c.spi) .. '@' .. c.waits end;"
        " return table.concat(t, ' ')"
    )


@pytest.fixture
def enemy_h(harness):
    harness.lua(r"""
      BAL = { towers = {} }
      SPAWN_CALLS = {}
      WAITS = {}
      local edb = require("entity_db")
      edb.entities.boss = { vis = { flags = F_BOSS } }
      edb.entities.a = {}
      edb.entities.b = {}
      local function stub_spawn(store, cmd, wave)
        local wait_time = cmd.wait_time
        if wait_time and wait_time > 0 then
          table.insert(WAITS, wait_time)
        end
        if store.force_next_wave then return end
        for _, o in ipairs(cmd.spawns or {}) do
          if store.force_next_wave then return end
          local idx_before = store.current_spawn_idx or 0
          store.current_spawn_idx = idx_before + 1
          local has_gems = false
          if store.gems_spawn_idx then
            for _, g in ipairs(store.gems_spawn_idx) do
              if g == store.current_spawn_idx then
                has_gems = true
                break
              end
            end
          end
          local ngems = has_gems and (store.gems_per_wave or 0) or 0
          table.insert(SPAWN_CALLS, {
            enemy = o.enemy,
            pi = o.pi,
            spi = o.spi,
            waits = #WAITS,
            wait_time = cmd.wait_time or 0,
            idx_before = idx_before,
            gems_per_wave = store.gems_per_wave,
            ngems = ngems,
          })
        end
      end
      local sys = { wave_spawn_tsv = { cmd_fns = { spawn = stub_spawn } } }
      package.loaded["systems"] = sys
      package.preload["systems"] = function() return sys end
      -- two roads like the game's: a middle rail and two edge rails 6 apart from it
      local function road(y)
        return {
          { { x = 0, y = y }, { x = 10, y = y } },
          { { x = 0, y = y + 6 }, { x = 10, y = y + 6 } },
          { { x = 0, y = y - 6 }, { x = 10, y = y - 6 } },
        }
      end
      package.loaded["path_db"] = { paths = { road(0), road(100) } }
    """)
    harness.write_data([])
    harness.write_live()
    harness.run_level()
    return harness


def test_identity_at_1(enemy_h):
    assert spawn(enemy_h, ["a", "b"], 1) == "2"


def test_double(enemy_h):
    assert spawn(enemy_h, ["a", "b"], 2, spi="2") == "4"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "2"
    # each copy walks beside its original: no extra waits, the next line over
    assert lanes_and_rows(enemy_h) == "2@1 1@1 2@1 1@1"
    assert enemy_h.lua("return #LAST_CMD.spawns") == "2"


def test_half_keeps_indices(enemy_h):
    assert spawn(enemy_h, ["a", "b", "a", "b"], 0.5) == "2"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "4"
    assert enemy_h.lua("return SPAWN_CALLS[1].enemy .. ',' .. SPAWN_CALLS[2].enemy") == "a,b"


def test_one_and_half(enemy_h):
    first = spawn(enemy_h, ["a", "b"], 1.5)
    second = spawn(enemy_h, ["a", "b"], 1.5, reset_acc=False)
    assert first == "2"
    assert second == "4"


def test_boss_never_multiplied(enemy_h):
    assert spawn(enemy_h, ["boss"], 3) == "1" and spawn(enemy_h, ["boss"], 0.5) == "1"


def test_carrier_kept_and_gems_scaled(enemy_h):
    assert spawn(enemy_h, ["a"], 0.5, gems_idx=(1,)) == "1"
    assert enemy_h.lua("return SPAWN_CALLS[1].gems_per_wave") == "5"
    assert enemy_h.lua("return LAST_STORE.gems_per_wave") == "10"
    spawn(enemy_h, ["a"], 2, gems_idx=(1,))
    assert enemy_h.lua("return SPAWN_CALLS[1].gems_per_wave .. ',' .. SPAWN_CALLS[2].ngems") == "20,0"


def test_wait_only_on_first(enemy_h):
    spawn(enemy_h, ["a", "b"], 1.5, wait=2)
    assert enemy_h.lua("return WAITS[1]") == "2"
    assert enemy_h.lua("return SPAWN_CALLS[1].wait_time .. ',' .. SPAWN_CALLS[#SPAWN_CALLS].wait_time") == "0,0"


def test_installed_once(enemy_h):
    enemy_h.run_level()
    enemy_h.run_level()
    assert spawn(enemy_h, ["a"], 2) == "2"


def test_plan_directly(enemy_h):
    out = enemy_h.lua("""
      local M = dofile(KRMOD.base .. "/mods/kr_mod/enemies.lua")
      local K = { enemy_acc = {} }
      local n_boss = M.plan(K, 3, "boss", "1|boss")
      local acc_boss = K.enemy_acc["1|boss"] or 0
      local n1 = M.plan(K, 0.5, "normal", "1|a")
      local acc1 = K.enemy_acc["1|a"] or 0
      local n2 = M.plan(K, 0.5, "normal", "1|a")
      local acc2 = K.enemy_acc["1|a"] or 0
      local n_car = M.plan(K, 0.5, "carrier", "1|c")
      local acc_car = K.enemy_acc["1|c"] or 0
      return string.format("%d,%g:%d,%g:%d,%g:%d,%g", n_boss, acc_boss, n1, acc1, n2, acc2, n_car, acc_car)
    """)
    assert out == "1,0:0,0.5:1,0:1,-0.5"


def test_force_next_wave_stops_spawning(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 2; KRMOD.enemy_acc = {}; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10, force_next_wave = true }
      local cmd = { wait_time = 1.0, spawns = { {pi=1,spi=1,enemy="a"}, {pi=1,spi=1,enemy="b"} } }
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      return #SPAWN_CALLS
    """)
    assert out == "0"


def test_missing_template_on_zero_plan(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 0.5; KRMOD.enemy_acc = {}; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10 }
      local cmd = { wait_time = 1.0, spawns = { {pi=1,spi=1,enemy="missing"} } }
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      return store.current_spawn_idx
    """)
    assert out == "0"


def test_live_enemy_mult_updates_mid_level(enemy_h):
    assert spawn(enemy_h, ["a"], 1) == "1"
    assert spawn(enemy_h, ["a"], 2) == "2"
    assert spawn(enemy_h, ["a"], 3) == "3"


def test_boss_mixed_with_normal_accumulator(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 0.5; KRMOD.enemy_acc = {}; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10 }
      local cmd = { wait_time = 1.0, spawns = { {pi=1,spi=1,enemy="boss"}, {pi=1,spi=1,enemy="a"} } }
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      return #SPAWN_CALLS .. "," .. tostring(KRMOD.enemy_acc["1|a"]) .. "," .. tostring(store.current_spawn_idx)
    """)
    assert out == "1,0.5,2"


def test_two_path_half_mult_spawns_both_paths(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 0.5; KRMOD.enemy_acc = {}; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10 }
      for i = 1, 4 do
        local cmd = {
          wait_time = 0,
          spawns = {
            { pi = 1, spi = 1, enemy = "a" },
            { pi = 2, spi = 1, enemy = "a" }
          }
        }
        require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      end
      local p1, p2 = 0, 0
      for _, call in ipairs(SPAWN_CALLS) do
        if call.pi == 1 then p1 = p1 + 1 end
        if call.pi == 2 then p2 = p2 + 1 end
      end
      return p1 .. "," .. p2
    """)
    assert out == "2,2"


def test_all_zero_command_still_waits(enemy_h):
    spawn(enemy_h, ["a"], 0.5, wait=3.0)
    assert enemy_h.lua("return #SPAWN_CALLS") == "0"
    assert enemy_h.lua("return WAITS[1]") == "3"


def test_quarter_over_eight_entries_on_one_stream_spawns_two(enemy_h):
    assert spawn(enemy_h, ["a"] * 8, 0.25) == "2"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "8"
    # the stream keeps no leftover: 8 x 0.25 is exactly 2
    assert enemy_h.lua("return tostring(KRMOD.enemy_acc['1|a'])") == "0"


def test_quarter_accumulator_carries_across_commands(enemy_h):
    assert spawn(enemy_h, ["a"] * 3, 0.25) == "0"
    assert spawn(enemy_h, ["a"] * 3, 0.25, reset_acc=False) == "1"


def test_ten_spawns_ten_per_normal_entry_in_rows_of_three(enemy_h):
    assert spawn(enemy_h, ["a", "b", "a"], 10) == "30"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "3"
    # one wait for the command, then rows of 3 (4 rows for 10): 3 spacing waits per entry
    assert enemy_h.lua("return #WAITS") == str(1 + 3 * 3)
    assert enemy_h.lua("return WAITS[2]") == "0.25"


def test_ten_boss_still_one_and_carrier_scaled(enemy_h):
    assert spawn(enemy_h, ["boss", "a"], 10) == "11"
    assert spawn(enemy_h, ["a"], 10, gems_idx=(1,)) == "10"
    assert enemy_h.lua("return SPAWN_CALLS[1].gems_per_wave") == "100"


def test_hundred_spawns_hundred_per_entry_and_keeps_boss_single(enemy_h):
    assert spawn(enemy_h, ["boss", "a"], 100) == "101"
    assert enemy_h.lua("return #WAITS") == str(1 + 16)  # 17 rows of up to 6


def first(h, count):
    return lanes_and_rows(h).split()[:count]


def test_rows_fill_the_three_rails_starting_from_the_originals(enemy_h):
    assert spawn(enemy_h, ["a"], 5, spi="2") == "5"
    # left edge, middle, right edge
    assert lanes_and_rows(enemy_h) == "2@1 1@1 3@1 2@2 1@2"
    assert enemy_h.lua("return tostring(next(require('path_db').paths[1], 3))") == "nil"


def test_middle_rail_original_keeps_it_in_three_lines(enemy_h):
    assert spawn(enemy_h, ["a"], 4, spi="1") == "4"
    assert lanes_and_rows(enemy_h) == "1@1 3@1 2@1 1@2"


def test_thirty_walk_in_four_lines(enemy_h):
    assert spawn(enemy_h, ["a"], 30, spi="2") == "30"
    assert first(enemy_h, 5) == ["2@1", "141@1", "142@1", "3@1", "2@2"]


def test_middle_rail_original_joins_the_four_lines(enemy_h):
    assert spawn(enemy_h, ["a"], 30, spi="1") == "30"
    assert sorted(first(enemy_h, 4)) == ["141@1", "142@1", "2@1", "3@1"]


def test_inner_rails_sit_a_third_of_the_way_to_each_edge(enemy_h):
    spawn(enemy_h, ["a"], 30, spi="2")
    out = enemy_h.lua("""
      local P = require("path_db")
      local t = {}
      for pi = 1, 2 do
        local l, r = P.paths[pi][141], P.paths[pi][142]
        t[#t + 1] = #P.paths[pi] .. ":" .. l[2].x .. "," .. l[2].y .. "/" .. r[2].x .. "," .. r[2].y
      end
      return table.concat(t, " ")
    """)
    # the game's own lua51.dll still counts 3 rails, so its random rail picks never use them
    assert out == "3:10,2/10,-2 3:10,102/10,98"


def test_raising_enemies_mid_level_keeps_the_earlier_rails(enemy_h):
    # enemies already walking the 4-line rails must still find them after x70 adds 6 lines
    spawn(enemy_h, ["a"], 30, spi="2")
    assert spawn(enemy_h, ["a"], 70, spi="2", reset_acc=False) == "70"
    out = enemy_h.lua("""
      local road = require("path_db").paths[1]
      local t = {}
      for _, k in ipairs({ 141, 142, 161, 162, 163, 164 }) do t[#t + 1] = road[k] and "y" or "n" end
      return #road .. ":" .. table.concat(t)
    """)
    assert out == "3:yyyyyy"


def test_new_level_roads_get_rails_again(enemy_h):
    spawn(enemy_h, ["a"], 30, spi="2")
    enemy_h.lua("""
      local P = require("path_db")
      P.paths = { { { { x = 0, y = 0 } }, { { x = 0, y = 3 } }, { { x = 0, y = -3 } } } }
    """)
    assert spawn(enemy_h, ["a"], 30, spi="2") == "30"
    assert first(enemy_h, 4) == ["2@1", "141@1", "142@1", "3@1"]
    assert enemy_h.lua("return require('path_db').paths[1][141][1].y") == "1"


def test_roads_with_other_rails_keep_their_own_lines(enemy_h):
    # one road with a single rail: no road gets inner rails (an enemy keeps its rail number
    # on the next road), and the other road's rows use its 3 rails
    enemy_h.lua("""
      local P = require("path_db")
      P.paths = { P.paths[1], { { { x = 0, y = 0 } } } }
    """)
    assert spawn(enemy_h, ["a"], 30, spi="2") == "30"
    assert first(enemy_h, 4) == ["2@1", "3@1", "1@1", "2@2"]
    assert enemy_h.lua("return tostring(require('path_db').paths[1][141])") == "nil"


def test_one_lane_road_spawns_copies_one_behind_another(enemy_h):
    enemy_h.lua('require("path_db").paths = { { { { x = 0, y = 0 } } } }')
    assert spawn(enemy_h, ["a"], 3) == "3"
    assert lanes_and_rows(enemy_h) == "1@1 1@2 1@3"


def test_random_lane_entry_still_fills_all_three_lanes_at_once(enemy_h):
    assert spawn(enemy_h, ["a"], 3, spi='"*"') == "3"
    assert sorted(lanes_and_rows(enemy_h).split()) == ["1@1", "2@1", "3@1"]


@pytest.mark.parametrize("mult, lines", [
    (2, 3), (29.9, 3), (30, 4), (49, 4), (50, 5), (69, 5), (70, 6), (100, 6),
])
def test_more_enemies_more_lines(enemy_h, mult, lines):
    code = f'return dofile(GAME_DIR .. "/mods/kr_mod/enemies.lua").lines_for({mult})'
    assert enemy_h.lua(code) == str(lines)


def test_fifty_walk_in_five_lines_keeping_the_middle_rail(enemy_h):
    assert spawn(enemy_h, ["a"], 50, spi="1") == "50"
    # 5 lines: edge, halfway, the middle rail itself, halfway, edge
    assert first(enemy_h, 6) == ["1@1", "153@1", "3@1", "2@1", "151@1", "1@2"]
    out = enemy_h.lua("local P = require('path_db'); return P.paths[1][151][2].y .. ',' .. P.paths[1][153][2].y")
    assert out == "3,-3"


def test_seventy_walk_in_six_lines(enemy_h):
    assert spawn(enemy_h, ["a"], 70, spi="2") == "70"
    assert first(enemy_h, 7) == ["2@1", "161@1", "162@1", "163@1", "164@1", "3@1", "2@2"]
    out = enemy_h.lua("""
      local P = require("path_db"); local t = {}
      for k = 161, 164 do t[#t + 1] = string.format("%.1f", P.paths[2][k][1].y) end
      return #P.paths[2] .. ":" .. table.concat(t, ",")
    """)
    assert out == "3:103.6,101.2,98.8,96.4"


def test_single_enemy_keeps_its_random_lane_for_the_game(enemy_h):
    assert spawn(enemy_h, ["a"], 1.5, spi='"*"') == "1"
    assert lanes_and_rows(enemy_h) == "*@1"


def test_unknown_lane_keeps_the_entry_and_spawns_in_line(enemy_h):
    assert spawn(enemy_h, ["a"], 3, spi="7") == "3"
    assert lanes_and_rows(enemy_h) == "7@1 7@2 7@3"


def test_quarter_boss_and_carrier_never_dropped(enemy_h):
    assert spawn(enemy_h, ["boss"], 0.25) == "1"
    assert spawn(enemy_h, ["a"], 0.25, gems_idx=(1,)) == "1"
    assert enemy_h.lua("return SPAWN_CALLS[1].gems_per_wave") == "2.5"
