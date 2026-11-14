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


def test_live_writes_file_and_saves(state):
    state.set_live(speed=3, troop_delta=2)
    assert "speed = 3" in (state.paths.mods_dir / "kr_mod_live.lua").read_text()
    assert ProfileStore(state.paths.profiles_dir).active().live.troop_delta == 2
    with pytest.raises(ProfileError):
        state.set_live(enemy_mult=0.6)
    with pytest.raises(ProfileError):
        state.set_live(troop_delta=101)


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


def test_all_enemies_scales_every_enemy_and_boss(state):
    goblin_speed = ("enemies", "orcs", "goblin", "speed")  # 50
    boss_speed = ("enemies", "lord_blackburn_boss", "speed")  # 12
    jt_hp = ("enemies", "jt_boss", "hp", 4)  # 11000
    goblin_hp = ("enemies", "orcs", "goblin", "hp", 1)  # 20
    assert "All moving speed" in state.card_categories("enemies/all")
    state.scale_card("enemies/all", "All moving speed", 50)
    state.scale_card("enemies/all", "All HP", 200)
    assert (state.current(goblin_speed), state.current(boss_speed)) == (25, 6)
    assert (state.current(goblin_hp), state.current(jt_hp)) == (40, 22000)
    assert state.card_pct("enemies/all", "All moving speed") == 50.0
    # one enemy edited by hand makes the box mixed; the reset puts every speed back
    state.set_value(goblin_speed, 60)
    assert state.card_pct("enemies/all", "All moving speed") is None
    assert state.card_category_changed("enemies/all", "All moving speed")
    state.reset_card_category("enemies/all", "All moving speed")
    assert (state.current(goblin_speed), state.current(boss_speed)) == (50, 12)
    assert not state.card_category_changed("enemies/all", "All moving speed")
    assert state.current(goblin_hp) == 40  # other kinds keep their edits


def test_all_range_widens_reach_only(state):
    # The sniper's blind spot, retarget jumps and unlimited max range stay the game's.
    state.scale_card("towers/sniper", "All range", 120)
    changed = set(state.profile.changes)
    assert ("towers", "sniper", "stats", "range") in changed
    for p in (
        ("towers", "sniper", "basic_attack", "min_range", 1),
        ("towers", "sniper", "basic_attack", "max_range", 1),
        ("towers", "sniper", "basic_attack", "max_retarget_range"),
        ("towers", "sniper", "ultimate", "retarget_range"),
    ):
        assert p not in changed
    assert state.card_pct("towers/sniper", "All range") == 120


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


def test_set_rule_and_speed_keys(state):
    assert not state.profile.unlock_tower_levels
    state.set_rule("unlock_tower_levels", True)
    state.set_rule("extra_hero_points", 40)
    saved = ProfileStore(state.paths.profiles_dir).active()
    assert (saved.unlock_tower_levels, saved.extra_hero_points) == (True, 40)
    with pytest.raises(ProfileError):
        state.set_rule("extra_hero_points", 1000)
    assert state.profile.extra_hero_points == 40

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


def test_duplicate_profile_with_explicit_source(state):
    state.new_profile("SourceProf")
    p = state.duplicate_profile("SourceProf", "DestProf")
    assert p.name == "DestProf"
    assert "DestProf" in state.profile_names()


def test_scale_row_noise_original_roundtrip_zero_changes(state):
    row = next(
        r for r in state.rows("towers/kr1/engineers")
        if any(state.original(p) == 62.400000000000006 for p in r.cells if p)
    )
    state.scale_row(row, 50.0)
    assert state.change_count() > 0
    state.scale_row(row, 100.0)
    assert state.change_count() == 0


def test_scale_row_at_zero_sets_zero_and_back_to_100_leaves_no_changes(state):
    row = next(r for r in state.rows("towers/archers") if r.id == "price")
    state.scale_row(row, 0.0)
    for p in row.cells:
        assert state.current(p) == 0.0
    assert state.change_count() > 0
    state.scale_row(row, 100.0)
    for p in row.cells:
        assert state.current(p) == state.original(p)
    assert state.change_count() == 0


def test_speed_click_bumps_live_seq_other_edits_keep_it(state):
    live_file = state.paths.mods_dir / "kr_mod_live.lua"

    def seq():
        return int(live_file.read_text().split("seq = ")[1].split(" ")[0])

    state.set_live(speed=1)
    first = seq()
    state.set_live(enemy_mult=2.0)
    assert seq() == first
    state.set_live(speed=1)
    assert seq() > first


def test_row_pct_keeps_a_step_that_rounds_back_to_the_same_values(state):
    # Small decimals round the same for many percents: 99% of 0.05 is still 0.05. The box must
    # still show the stepped percent, or the arrows could never leave 100%.
    row, card = next(
        (r, cid)
        for cid in (c.id for c in state.index.cards("Heroes"))
        for r in state.rows(cid)
        if state.row_scalable(r)
        and all(0 < state.original(p) <= 0.1 for p in r.cells if p is not None)
    )
    cells = [p for p in row.cells if p is not None]
    state.scale_row(row, 99)
    assert state.row_pct(row) == 99
    assert [state.current(p) for p in cells] == [scale(state.original(p), 99) for p in cells]
    state.scale_row(row, 60)
    assert state.row_pct(row) == 60
    # An edit that breaks the remembered percent falls back to reading the values.
    state.set_value(cells[0], 0.5)
    assert state.row_pct(row) != 60
    state.reset_all()
    assert state.row_pct(row) == 100
