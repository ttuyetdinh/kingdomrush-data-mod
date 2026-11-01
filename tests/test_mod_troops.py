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
