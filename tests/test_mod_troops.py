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


def test_scale_from_base_no_compounding(troop_h):
    troop_h.lua("B = { max_soldiers = 3 }; T = require('kr_mod_troops_under_test')")
    for _ in range(3):
        troop_h.lua("T.apply_barrack(B, 2)")
    assert troop_h.lua("return B.max_soldiers") == "6"
    troop_h.lua("T.apply_barrack(B, 1)")
    assert troop_h.lua("return B.max_soldiers") == "3"


def test_script_rewrite_becomes_base(troop_h):
    troop_h.lua(
        "B = { max_soldiers = 3 }; T.apply_barrack(B, 2); B.max_soldiers = 4; T.apply_barrack(B, 2)"
    )
    assert troop_h.lua("return B.max_soldiers") == "8"


@pytest.mark.parametrize(
    "base,mult,out",
    [(3, 1.5, 5), (1, 0.5, 1), (8, 3, 24), (2, 0.5, 1)],
)
def test_rounding(troop_h, base, mult, out):
    assert (
        troop_h.lua(
            f"local b = {{ max_soldiers = {base} }}; T.apply_barrack(b, {mult}); return b.max_soldiers"
        )
        == str(out)
    )


def test_per_level_table(troop_h):
    troop_h.lua(
        "B = { max_soldiers = { 2, 3, 4 } }; T.apply_barrack(B, 2); T.apply_barrack(B, 2)"
    )
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,6,8"


def test_templates_and_live_entities(troop_h):
    troop_h.lua(
        """local E = require('entity_db'); E.entities.knights = { barrack = { max_soldiers = 3 } }
      game.store.entities[7] = { barrack = { max_soldiers = 3 } }; game.store.entities[8] = { hp = 1 }
      KRMOD.live.troop_mult = 2; KRMOD.pollers.troops(KRMOD)"""
    )
    assert (
        troop_h.lua("return require('entity_db').entities.knights.barrack.max_soldiers")
        == "6"
    )
    assert troop_h.lua("return game.store.entities[7].barrack.max_soldiers") == "6"
    assert "troops x2: 2 barracks" in troop_h.log()


def test_copied_template_keeps_base(troop_h):
    troop_h.lua(
        "B = { max_soldiers = 3 }; T.apply_barrack(B, 2); C = { max_soldiers = B.max_soldiers, _kr_base = B._kr_base, _kr_applied = B._kr_applied }; T.apply_barrack(C, 1)"
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
    assert troop_h.lua("return B3.max_soldiers[3]") == "8"


def test_poller_logging_only_on_change(troop_h):
    troop_h.lua(
        """local E = require('entity_db'); E.entities.knights = { barrack = { max_soldiers = 3 } }
      KRMOD.live.troop_mult = 2; KRMOD.pollers.troops(KRMOD)"""
    )
    log1 = troop_h.log()
    assert "troops x2: 1 barracks" in log1

    troop_h.lua("KRMOD.pollers.troops(KRMOD)")
    log2 = troop_h.log()
    assert log2.count("troops x2: 1 barracks") == 1

    troop_h.lua("KRMOD.live.troop_mult = 1.5; KRMOD.pollers.troops(KRMOD)")
    log3 = troop_h.log()
    assert "troops x1.5: 1 barracks" in log3


def test_nil_barrack_or_mult(troop_h):
    assert troop_h.lua("return tostring(T.apply_barrack(nil, 2))") == "false"
    assert troop_h.lua("return tostring(T.apply_barrack({}, nil))") == "false"


def test_per_level_table_script_rewrite(troop_h):
    troop_h.lua("B = { max_soldiers = { 2, 3, 4 } }; T.apply_barrack(B, 2)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,6,8"
    troop_h.lua("B.max_soldiers[2] = 5; T.apply_barrack(B, 2)")
    assert troop_h.lua("return table.concat(B.max_soldiers, ',')") == "4,10,8"


def test_apply_all_odd_store_shapes(troop_h):
    troop_h.lua(
        """require('entity_db').entities = nil
      game.store.entities = nil
      KRMOD.live.troop_mult = 2
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
      KRMOD.live.troop_mult = 2
      count = KRMOD.pollers.troops(KRMOD)"""
    )
    assert troop_h.lua("return tostring(count)") == "1"
    assert troop_h.lua("return require('entity_db').entities.good.barrack.max_soldiers") == "6"
    log = troop_h.log()
    assert "error troops: " in log
    assert "boom" in log
    assert "troops x2: 1 barracks" in log


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


@pytest.mark.parametrize("mult,out", [(1.5, 3), (2, 4), (2.25, 5), (3, 6)])
def test_camp_level2_upgrade(camp_h, mult, out):
    camp_h.lua(f"KRMOD.live.troop_mult = {mult}")
    camp_h.lua("camp_level(1)")
    assert camp_h.lua("return camp_level(2)") == f"{out},{out}"


def test_camp_upgrade_sequence_at_x2(camp_h):
    camp_h.lua("KRMOD.live.troop_mult = 2")
    assert camp_h.lua("return camp_level(1)") == "2,2"
    assert camp_h.lua("return camp_level(2)") == "4,4"
    assert camp_h.lua("KRMOD.pollers.troops(KRMOD); return camp_level(2)") == "4,4"
    camp_h.lua("KRMOD.live.troop_mult = 1; KRMOD.pollers.troops(KRMOD)")
    assert camp_h.lua("return game.store.entities[1].barrack.max_soldiers") == "2"
    assert camp_h.lua("return camp_level(3)") == "2,2"
    # a barracks that is not the camp's own is left to the generic poller
    assert camp_h.lua("return game.store.entities[3].barrack.max_soldiers") == "5"


def test_camp_wrap_is_idempotent_and_keeps_results(camp_h):
    camp_h.run_level()
    camp_h.run_level()
    camp_h.lua(CAMP_ENTITIES)
    camp_h.lua("KRMOD.live.troop_mult = 2; camp_level(1)")
    assert camp_h.lua("return CAMP_CALLS") == "1"
    assert camp_h.lua("return tostring(r1) .. ',' .. tostring(r2)") == "true,second"
    assert camp_h.lua("return camp_level(2)") == "4,4"
    assert camp_h.lua("return CAMP_CALLS") == "2"


def test_camp_cleanup_error_logged_original_result_kept(camp_h):
    camp_h.lua(
        """KRMOD.live.troop_mult = 2
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
