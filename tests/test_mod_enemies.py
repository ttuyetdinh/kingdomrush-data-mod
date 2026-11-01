import pytest


def spawn(h, enemies, mult, gems_idx=(), wait=1.0):
    return h.lua(
        f"""KRMOD.live.enemy_mult = {mult}; KRMOD.enemy_acc = 0; SPAWN_CALLS = {{}}; WAITS = {{}}
      local store = {{ current_spawn_idx = 0, gems_spawn_idx = {{ {",".join(map(str, gems_idx))} }}, gems_per_wave = 10 }}
      local cmd = {{ wait_time = {wait}, spawns = {{ {",".join(f'{{pi=1,spi=1,enemy="{e}"}}' for e in enemies)} }} }}
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      LAST_STORE = store; LAST_CMD = cmd; return #SPAWN_CALLS"""
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
    assert enemy_h.lua("return WAITS[1]") == "0.25" and enemy_h.lua("return #LAST_CMD.spawns") == "2"


def test_half_keeps_indices(enemy_h):
    assert spawn(enemy_h, ["a", "b", "a", "b"], 0.5) == "2"
    assert enemy_h.lua("return LAST_STORE.current_spawn_idx") == "4"


def test_one_and_half(enemy_h):
    assert spawn(enemy_h, ["a", "b"], 1.5) == "3"


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
    assert enemy_h.lua("return SPAWN_CALLS[1].wait_time .. ',' .. SPAWN_CALLS[3].wait_time") == "2,0"


def test_installed_once(enemy_h):
    enemy_h.run_level()
    enemy_h.run_level()
    assert spawn(enemy_h, ["a"], 2) == "2"


def test_plan_directly(enemy_h):
    out = enemy_h.lua("""
      local M = dofile(KRMOD.base .. "/mods/kr_mod/enemies.lua")
      local K = { enemy_acc = 0 }
      local n_boss = M.plan(K, 3, "boss")
      local acc_boss = K.enemy_acc
      local n1 = M.plan(K, 0.5, "normal")
      local acc1 = K.enemy_acc
      local n2 = M.plan(K, 0.5, "normal")
      local acc2 = K.enemy_acc
      local n_car = M.plan(K, 0.5, "carrier")
      local acc_car = K.enemy_acc
      return string.format("%d,%g:%d,%g:%d,%g:%d,%g", n_boss, acc_boss, n1, acc1, n2, acc2, n_car, acc_car)
    """)
    assert out == "1,0:0,0.5:1,0:1,-0.5"


def test_force_next_wave_stops_spawning(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 2; KRMOD.enemy_acc = 0; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10, force_next_wave = true }
      local cmd = { wait_time = 1.0, spawns = { {pi=1,spi=1,enemy="a"}, {pi=1,spi=1,enemy="b"} } }
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      return #SPAWN_CALLS
    """)
    assert out == "0"


def test_missing_template_on_zero_plan(enemy_h):
    out = enemy_h.lua("""
      KRMOD.live.enemy_mult = 0.5; KRMOD.enemy_acc = 0; SPAWN_CALLS = {}; WAITS = {}
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
      KRMOD.live.enemy_mult = 0.5; KRMOD.enemy_acc = 0; SPAWN_CALLS = {}; WAITS = {}
      local store = { current_spawn_idx = 0, gems_spawn_idx = {}, gems_per_wave = 10 }
      local cmd = { wait_time = 1.0, spawns = { {pi=1,spi=1,enemy="boss"}, {pi=1,spi=1,enemy="a"} } }
      require("systems").wave_spawn_tsv.cmd_fns.spawn(store, cmd, "w1")
      return #SPAWN_CALLS .. "," .. tostring(KRMOD.enemy_acc) .. "," .. tostring(store.current_spawn_idx)
    """)
    assert out == "1,0.5,2"
