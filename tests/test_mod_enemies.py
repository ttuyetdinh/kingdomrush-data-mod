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
      -- road 1 has three lanes, road 2 only one
      package.loaded["path_db"] = { paths = { { {}, {}, {} }, { {} } } }
    """)
    harness.write_data([])
    harness.write_live()
    harness.run_level()
    return harness


def test_identity_at_1(enemy_h):
    assert spawn(enemy_h, ["a", "b"], 1) == "2"


def test_double(enemy_h):
    assert spawn(enemy_h, ["a", "b"], 2) == "4"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "2"
    # each copy walks beside its original: no extra waits, the next lane over
    assert lanes_and_rows(enemy_h) == "1@1 2@1 1@1 2@1"
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
    assert enemy_h.lua("return #WAITS") == str(1 + 33)  # 34 rows of up to 3


def test_rows_fill_every_lane_starting_from_the_originals(enemy_h):
    assert spawn(enemy_h, ["a"], 5, spi="2") == "5"
    assert lanes_and_rows(enemy_h) == "2@1 3@1 1@1 2@2 3@2"


def test_one_lane_road_spawns_copies_one_behind_another(enemy_h):
    assert spawn(enemy_h, ["a"], 3, pi=2) == "3"
    assert lanes_and_rows(enemy_h) == "1@1 1@2 1@3"


def test_random_lane_entry_still_fills_all_three_lanes_at_once(enemy_h):
    assert spawn(enemy_h, ["a"], 3, spi='"*"') == "3"
    lanes = lanes_and_rows(enemy_h).split()
    assert sorted(lanes) == ["1@1", "2@1", "3@1"]


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
