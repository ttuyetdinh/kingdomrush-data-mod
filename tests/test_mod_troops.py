import pytest


@pytest.fixture
def troop_h(harness):
    harness.lua("BAL = {}")
    harness.write_data([])
    harness.run_level()
    harness.lua(
        'package.preload["kr_mod_troops_under_test"] = function() '
        '  return dofile(KRMOD.base .. "/mods/kr_mod/troops.lua") '
        "end; "
        'local ok, mod = pcall(require, "kr_mod_troops_under_test"); '
        "if ok then T = mod end"
    )
    yield harness


def test_add_from_base_no_compounding(troop_h):
    troop_h.lua("B = { max_soldiers = 3 }; T = require('kr_mod_troops_under_test')")
    for _ in range(3):
        troop_h.lua("T.apply_barrack(B, 2)")
    assert troop_h.lua("return B.max_soldiers") == "5"
    troop_h.lua("T.apply_barrack(B, -1)")
    assert troop_h.lua("return B.max_soldiers") == "2"
    troop_h.lua("T.apply_barrack(B, 0)")
    assert troop_h.lua("return B.max_soldiers") == "3"


def test_script_rewrite_becomes_base(troop_h):
    troop_h.lua(
        "B = { max_soldiers = 3 }; T.apply_barrack(B, 2); B.max_soldiers = 4; T.apply_barrack(B, 2)"
    )
    assert troop_h.lua("return B.max_soldiers") == "6"


@pytest.mark.parametrize(
    "base,delta,out",
    [(3, 2, 5), (3, -1, 2), (3, 0, 3), (8, 10, 18), (1, -1, 0), (3, -5, 0), (2, -10, 0)],
)
def test_target_is_base_plus_delta_never_below_zero(troop_h, base, delta, out):
    assert (
        troop_h.lua(
            f"local b = {{ max_soldiers = {base} }}; T.apply_barrack(b, {delta}); return b.max_soldiers"
        )
        == str(out)
    )


def test_empty_barracks_recovers_when_delta_rises(troop_h):
    troop_h.lua("B = { max_soldiers = 3 }; T.apply_barrack(B, -5)")
    assert troop_h.lua("return B.max_soldiers") == "0"
    troop_h.lua("T.apply_barrack(B, -5)")
    assert troop_h.lua("return B.max_soldiers") == "0"
    troop_h.lua("T.apply_barrack(B, 0)")
    assert troop_h.lua("return B.max_soldiers") == "3"
    # a game rewrite while the barracks is empty becomes the new base
    troop_h.lua("T.apply_barrack(B, -5); B.max_soldiers = 4; T.apply_barrack(B, -1)")
    assert troop_h.lua("return B.max_soldiers") == "3"


def test_per_level_table(troop_h):
    troop_h.lua(
        "B = { max_soldiers = { 2, 3, 4 } }; T.apply_barrack(B, 2); T.apply_barrack(B, 2)"
    )
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,5,6"
    troop_h.lua("T.apply_barrack(B, -3)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "0,0,1"
    troop_h.lua("T.apply_barrack(B, 0)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "2,3,4"


def test_templates_and_live_entities(troop_h):
    troop_h.lua(
        """local E = require('entity_db'); E.entities.knights = { barrack = { max_soldiers = 3 } }
      game.store.entities[7] = { barrack = { max_soldiers = 3 } }; game.store.entities[8] = { hp = 1 }
      KRMOD.live.troop_delta = 2; KRMOD.pollers.troops(KRMOD)"""
    )
    assert (
        troop_h.lua("return require('entity_db').entities.knights.barrack.max_soldiers")
        == "5"
    )
    assert troop_h.lua("return game.store.entities[7].barrack.max_soldiers") == "5"
    assert "troops +2: 2 barracks" in troop_h.log()


def test_copied_template_keeps_base(troop_h):
    troop_h.lua(
        "B = { max_soldiers = 3 }; T.apply_barrack(B, 2); C = { max_soldiers = B.max_soldiers, _kr_base = B._kr_base, _kr_applied = B._kr_applied }; T.apply_barrack(C, 0)"
    )
    assert troop_h.lua("return C.max_soldiers") == "3"


def test_odd_shapes_skipped(troop_h):
    troop_h.lua("B1 = { hp = 10 }; res1 = T.apply_barrack(B1, 2)")
    assert troop_h.lua("return tostring(res1)") == "false"
    assert troop_h.lua("return tostring(B1.max_soldiers)") == "nil"

    troop_h.lua("B2 = { max_soldiers = 'invalid' }; res2 = T.apply_barrack(B2, 2)")
    assert troop_h.lua("return tostring(res2)") == "false"
    assert troop_h.lua("return tostring(B2.max_soldiers)") == "invalid"

    troop_h.lua("B3 = { max_soldiers = { 2, 'skip', 4 } }; res3 = T.apply_barrack(B3, 2)")
    assert troop_h.lua("return tostring(res3)") == "true"
    assert troop_h.lua("return B3.max_soldiers[1]") == "4"
    assert troop_h.lua("return B3.max_soldiers[2]") == "skip"
    assert troop_h.lua("return B3.max_soldiers[3]") == "6"


def test_poller_logging_only_on_change(troop_h):
    troop_h.lua(
        """local E = require('entity_db'); E.entities.knights = { barrack = { max_soldiers = 3 } }
      KRMOD.live.troop_delta = 2; KRMOD.pollers.troops(KRMOD)"""
    )
    assert "troops +2: 1 barracks" in troop_h.log()

    troop_h.lua("KRMOD.pollers.troops(KRMOD)")
    assert troop_h.log().count("troops +2: 1 barracks") == 1

    troop_h.lua("KRMOD.live.troop_delta = -1; KRMOD.pollers.troops(KRMOD)")
    assert "troops -1: 1 barracks" in troop_h.log()

    troop_h.lua("KRMOD.live.troop_delta = 0; KRMOD.pollers.troops(KRMOD)")
    assert "troops 0: 1 barracks" in troop_h.log()


def test_nil_barrack_or_delta(troop_h):
    assert troop_h.lua("return tostring(T.apply_barrack(nil, 2))") == "false"
    assert troop_h.lua("return tostring(T.apply_barrack({}, nil))") == "false"


def test_per_level_table_script_rewrite(troop_h):
    troop_h.lua("B = { max_soldiers = { 2, 3, 4 } }; T.apply_barrack(B, 2)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,5,6"
    troop_h.lua("B.max_soldiers[2] = 6; T.apply_barrack(B, 2)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,8,6"


def test_apply_all_odd_store_shapes(troop_h):
    troop_h.lua(
        """require('entity_db').entities = nil
      game.store.entities = nil
      KRMOD.live.troop_delta = 2
      count = KRMOD.pollers.troops(KRMOD)"""
    )
    assert troop_h.lua("return tostring(count)") == "0"


def test_apply_all_error_logged_and_continues(troop_h):
    troop_h.lua(
        """local E = require('entity_db')
      local bad_table = {}
      setmetatable(bad_table, { __index = function() error('boom') end })
      E.entities.bad = { barrack = bad_table }
      E.entities.good = { barrack = { max_soldiers = 3 } }
      KRMOD.live.troop_delta = 2
      count = KRMOD.pollers.troops(KRMOD)"""
    )
    assert troop_h.lua("return tostring(count)") == "1"
    assert troop_h.lua("return require('entity_db').entities.good.barrack.max_soldiers") == "5"
    log = troop_h.log()
    assert "error troops: " in log
    assert "boom" in log
    assert "troops +2: 1 barracks" in log


# Hand-built stand-in for the stage 11 camp tower: its insert writes the vanilla
# per-level soldier count (1, 2, 2) into every personal camp barrack.
CAMP_SETUP = """
CAMP_CALLS = 0
package.loaded['scripts_game'].tower_stage_11_camp.insert = function(this, store)
  CAMP_CALLS = CAMP_CALLS + 1
  for _, e in pairs(store.entities) do
    if e.template_name == this.barracks_t then
      e.barrack.max_soldiers = this.barracks_soldiers[this.tower.level]
    end
  end
  return true, 'second'
end
"""

CAMP_ENTITIES = """
game.store.entities = {
  [1] = { template_name = 'camp_barrack', barrack = { max_soldiers = 1 } },
  [2] = { template_name = 'camp_barrack', barrack = { max_soldiers = 1 } },
  [3] = { template_name = 'other_barrack', barrack = { max_soldiers = 5 } },
}
CAMP = { barracks_t = 'camp_barrack', barracks_soldiers = { 1, 2, 2 }, tower = { level = 1 } }
function camp_level(n)
  CAMP.tower.level = n
  r1, r2 = package.loaded['scripts_game'].tower_stage_11_camp.insert(CAMP, game.store)
  KRMOD.pollers.troops(KRMOD)
  return game.store.entities[1].barrack.max_soldiers .. ',' .. game.store.entities[2].barrack.max_soldiers
end
"""


@pytest.fixture
def camp_h(troop_h):
    troop_h.lua(CAMP_SETUP)
    troop_h.run_level()
    troop_h.lua(CAMP_ENTITIES)
    return troop_h


@pytest.mark.parametrize("delta,out", [(1, 3), (2, 4), (-1, 1), (-2, 0), (-10, 0), (10, 12)])
def test_camp_level2_upgrade(camp_h, delta, out):
    camp_h.lua(f"KRMOD.live.troop_delta = {delta}")
    camp_h.lua("camp_level(1)")
    assert camp_h.lua("return camp_level(2)") == f"{out},{out}"


def test_camp_upgrade_sequence_at_plus_2(camp_h):
    camp_h.lua("KRMOD.live.troop_delta = 2")
    assert camp_h.lua("return camp_level(1)") == "3,3"
    assert camp_h.lua("return camp_level(2)") == "4,4"
    assert camp_h.lua("KRMOD.pollers.troops(KRMOD); return camp_level(2)") == "4,4"
    camp_h.lua("KRMOD.live.troop_delta = 0; KRMOD.pollers.troops(KRMOD)")
    assert camp_h.lua("return game.store.entities[1].barrack.max_soldiers") == "2"
    assert camp_h.lua("return camp_level(3)") == "2,2"
    # a barracks that is not the camp's own is left to the generic poller
    assert camp_h.lua("return game.store.entities[3].barrack.max_soldiers") == "5"


def test_camp_empty_barracks_when_minus_exceeds_vanilla(camp_h):
    camp_h.lua("KRMOD.live.troop_delta = -1")
    assert camp_h.lua("return camp_level(1)") == "0,0"
    assert camp_h.lua("return camp_level(2)") == "1,1"
    assert camp_h.lua("return game.store.entities[3].barrack.max_soldiers") == "4"


def test_camp_wrap_is_idempotent_and_keeps_results(camp_h):
    camp_h.run_level()
    camp_h.run_level()
    camp_h.lua(CAMP_ENTITIES)
    camp_h.lua("KRMOD.live.troop_delta = 2; camp_level(1)")
    assert camp_h.lua("return CAMP_CALLS") == "1"
    assert camp_h.lua("return tostring(r1) .. ',' .. tostring(r2)") == "true,second"
    assert camp_h.lua("return camp_level(2)") == "4,4"
    assert camp_h.lua("return CAMP_CALLS") == "2"


def test_camp_cleanup_error_logged_original_result_kept(camp_h):
    camp_h.lua(
        """KRMOD.live.troop_delta = 2
      game.store.entities[1].barrack = setmetatable({ max_soldiers = 1 },
        { __newindex = function() error('boom') end })
      camp_level(1)"""
    )
    assert camp_h.lua("return tostring(r1)") == "true"
    log = camp_h.log()
    assert "error troops camp: " in log
    assert "boom" in log


def test_camp_hook_missing_logged(troop_h):
    troop_h.lua("package.loaded['scripts_game'] = nil")
    troop_h.run_level()
    assert "error troops: stage 11 camp hook not found" in troop_h.log()
