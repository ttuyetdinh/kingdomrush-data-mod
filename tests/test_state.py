import dataclasses
import math
import pytest

from krmod.model.categories import category_of
from krmod.model.grouping import GroupIndex
from krmod.model.scaling import scale
from krmod.modgen.launcher import RunOutcome
from krmod.modgen.writer import ApplyResult
from krmod.profiles import ProfileError, ProfileStore
from krmod.state import AppState


@pytest.fixture
def state(game_paths, tree, tmp_path):
    paths = dataclasses.replace(
        game_paths,
        mods_dir=tmp_path / "mods",
        profiles_dir=tmp_path / "profiles",
    )
    index = GroupIndex.build(tree)
    store = ProfileStore(paths.profiles_dir)
    return AppState(paths, tree, index, store)


def test_set_and_reset(state):
    p = ("towers", "archers", "price", 1)
    assert state.set_value(p, 7) is None and state.current(p) == 7 and state.change_count() == 1
    state.set_value(p, 70)
    assert state.change_count() == 0


def test_parse_and_set_rejects_bad_text(state):
    p = ("towers", "archers", "price", 1)
    for bad in ("", "abc", "1,5", "nan", "inf", "1_5", "١٢"):
        ok, _ = state.parse_and_set(p, bad)
        assert not ok and state.current(p) == 70
    assert state.parse_and_set(p, " 7 ") == (True, None)
    with pytest.raises(ValueError):
        state.set_value(("enemies", "demons", "demon_lord", "basic_attack", "damage_type"), 4)


def test_parse_and_set_reason_for_abc(state):
    p = ("towers", "archers", "price", 1)
    ok, reason = state.parse_and_set(p, "abc")
    assert not ok
    assert reason is not None
    assert "Not a number" in reason


def test_cooldown_zero_warns(state):
    row = next(r for r in state.rows("towers/archers") if "cooldown" in r.id)
    assert state.set_value(row.cells[0], 0)


def test_row_scale_and_position(state):
    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    state.scale_row(row, 50)
    assert state.current(row.cells[0]) == 35 and state.row_pct(row) == 50
    state.set_value(row.cells[0], 36)
    assert state.row_pct(row) is None
    state.scale_row(row, 100)
    assert state.change_count() == 0


def test_card_scale_covers_skills(state):
    state.scale_card("towers/knights", "All costs", 50)
    assert all(
        state.current(p) == scale(state.original(p), 50)
        for p in state.index.paths_of("towers/knights")
        if category_of(p) == "All costs"
    )


def test_locked_level_slider(state):
    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    state.set_level(row.cells[0], 140, locked_row=row)
    assert state.current(row.cells[1]) == scale(state.original(row.cells[1]), 200)


def test_live_writes_file_and_saves(state):
    state.set_live(speed=3, troop_mult=2)
    assert "speed = 3" in (state.paths.mods_dir / "kr_mod_live.lua").read_text()
    assert ProfileStore(state.paths.profiles_dir).active().live.troop_mult == 2
    with pytest.raises(ProfileError):
        state.set_live(enemy_mult=0.6)


def test_profile_switch_isolates_changes(state):
    state.set_value(("towers", "archers", "price", 1), 7)
    state.new_profile("Hard")
    state.switch_profile("Hard")
    assert state.change_count() == 0


def test_card_categories_and_pct(state):
    cats = state.card_categories("towers/archers")
    assert "All costs" in cats
    assert "All damage" in cats

    state.scale_card("towers/archers", "All costs", 50)
    assert state.card_pct("towers/archers", "All costs") == 50.0

    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    state.set_value(row.cells[0], 99)
    assert state.card_pct("towers/archers", "All costs") is None
    assert state.card_pct("towers/archers", "NonExistentCategory") is None


def test_set_value_validation(state):
    p = ("towers", "archers", "price", 1)
    with pytest.raises(ValueError):
        state.set_value(p, True)
    with pytest.raises(ValueError):
        state.set_value(p, "bad")
    with pytest.raises(ValueError):
        state.set_value(p, float("nan"))
    with pytest.raises(ValueError):
        state.set_value(p, float("inf"))
    with pytest.raises(ValueError):
        state.set_value(("invalid", "path"), 10)


def test_set_unlock_and_speed_keys(state):
    assert not state.profile.unlock_tower_levels
    state.set_unlock(True)
    assert state.profile.unlock_tower_levels
    assert ProfileStore(state.paths.profiles_dir).active().unlock_tower_levels

    state.set_speed_keys(["F5", "F6", "F7"])
    assert state.profile.speed_keys == ("f5", "f6", "f7")
    assert ProfileStore(state.paths.profiles_dir).active().speed_keys == ("f5", "f6", "f7")

    with pytest.raises(ProfileError):
        state.set_speed_keys(["f1", "f5", "f6"])


def test_profile_actions(state):
    assert state.profile_names() == ["Default"]
    p2 = state.new_profile("Modded")
    assert p2.name == "Modded"
    assert "Modded" in state.profile_names()

    state.switch_profile("Modded")
    assert state.profile.name == "Modded"

    p3 = state.duplicate_profile("Modded Copy")
    assert p3.name == "Modded Copy"
    assert "Modded Copy" in state.profile_names()

    state.rename_profile("Modded Copy", "Renamed")
    assert "Renamed" in state.profile_names()
    assert "Modded Copy" not in state.profile_names()

    state.delete_profile("Renamed")
    assert "Renamed" not in state.profile_names()

    with pytest.raises(ProfileError):
        state.switch_profile("NonExistent")


def test_reset_and_card_has_changes(state):
    p1 = ("towers", "archers", "price", 1)
    p2 = ("towers", "archers", "price", 2)
    card_id = "towers/archers"
    assert not state.card_has_changes(card_id)
    assert not state.is_changed(p1)

    state.set_value(p1, 10)
    state.set_value(p2, 20)
    assert state.card_has_changes(card_id)
    assert state.is_changed(p1)
    assert state.change_count() == 2

    state.reset(p1)
    assert not state.is_changed(p1)
    assert state.is_changed(p2)
    assert state.card_has_changes(card_id)
    assert state.change_count() == 1

    state.reset_all()
    assert state.change_count() == 0
    assert not state.card_has_changes(card_id)


def test_stale_changes(state):
    assert state.stale() == []
    fake_path = ("nonexistent", "path")
    state.profile.changes[fake_path] = 123.0
    state.store.save(state.profile)
    assert fake_path in state.stale()


def test_alias_note(state):
    p = ("towers", "archers", "price", 1)
    assert state.alias_note(p) is None

    target = ("towers", "rangers", "price")
    state.tree.aliases[("towers", "archers", "price")] = target
    try:
        assert state.alias_note(("towers", "archers", "price", 1)) == "linked with towers.rangers.price.1"
        assert state.alias_note(("towers", "rangers", "price", 1)) == "linked with towers.archers.price.1"
    finally:
        del state.tree.aliases[("towers", "archers", "price")]


def test_c2_range(state):
    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    rng = state.c2_range(row)
    assert rng == (0.0, 690.0)


def test_rows_caching(state):
    rows1 = state.rows("towers/archers")
    rows2 = state.rows("towers/archers")
    assert rows1 == rows2
    assert [r.id for r in rows1] == [r.id for r in rows2]


def test_apply_and_apply_and_run(state, monkeypatch):
    p = ("towers", "archers", "price", 1)
    state.set_value(p, 42)
    res = state.apply()
    assert isinstance(res, ApplyResult)
    assert res.applied == 1
    assert (state.paths.mods_dir / "kr_mod_data.lua").is_file()

    monkeypatch.setattr(
        "krmod.state.apply_and_run",
        lambda paths, prof, tr: (RunOutcome.LAUNCHED, res),
    )
    outcome, ares = state.apply_and_run()
    assert outcome == RunOutcome.LAUNCHED
    assert ares == res


def test_friendly_damage_bool_not_scaled(state):
    bool_path = ("specials", "terrain_2", "pillar_tower_holders", "friendly_damage")
    assert state.tree.leaves[bool_path].kind == "bool"
    state.scale_card("stages/terrain_2", "All damage", 50)
    assert not state.is_changed(bool_path)
    assert bool_path not in state.profile.changes


def test_set_value_on_bool_and_str(state):
    bool_path = ("specials", "terrain_2", "pillar_tower_holders", "friendly_damage")
    str_path = ("powers", "soaring_shop", "stats", "type")
    with pytest.raises(ValueError, match="cannot be edited as numeric"):
        state.set_value(bool_path, 1)
    with pytest.raises(ValueError, match="cannot be edited as numeric"):
        state.set_value(str_path, 1)


def test_row_pct_outside_range(state):
    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    state.scale_row(row, 400.0)
    assert state.row_pct(row) == 400.0


def test_parse_and_set_returns_warning(state):
    row = next(r for r in state.rows("towers/archers") if "cooldown" in r.id)
    ok, warn_msg = state.parse_and_set(row.cells[0], "0")
    assert ok
    assert warn_msg is not None
    assert "cooldown" in warn_msg.lower() or "break" in warn_msg.lower()


def test_set_level_zero_original_fallback(state):
    zero_path = ("synthetic", "test", "zero_stat")
    from krmod.model.values import Leaf
    state.tree.leaves[zero_path] = Leaf(path=zero_path, value=0.0, kind="num")
    try:
        from krmod.model.rows import StatRow
        row = StatRow(
            id="zero_stat",
            group="test",
            label="Zero Stat",
            cells=(zero_path,),
            is_enum=False,
            read_only=False,
        )
        state.set_level(zero_path, 5.0, locked_row=row)
        assert state.current(zero_path) == 5.0
    finally:
        state.tree.leaves.pop(zero_path, None)


def test_duplicate_profile_with_explicit_source(state):
    state.new_profile("SourceProf")
    p = state.duplicate_profile("SourceProf", "DestProf")
    assert p.name == "DestProf"
    assert "DestProf" in state.profile_names()


def test_locked_level_large_original_exact(state):
    row = next(
        r for r in state.rows("stages/stage_18")
        if r.id == "veznan.boss.hp_max"
    )
    p = row.cells[0]
    assert state.original(p) == 5666.0
    state.set_level(p, 5667, locked_row=row)
    assert state.current(p) == 5667


def test_scale_row_noise_original_roundtrip_zero_changes(state):
    row = next(
        r for r in state.rows("towers/kr1/engineers")
        if any(state.original(p) == 62.400000000000006 for p in r.cells if p)
    )
    state.scale_row(row, 50.0)
    assert state.change_count() > 0
    state.scale_row(row, 100.0)
    assert state.change_count() == 0
