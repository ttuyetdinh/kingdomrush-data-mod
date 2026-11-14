import json
import os

import pytest

from krmod.profiles import (
    LiveSettings,
    Profile,
    ProfileError,
    ProfileStore,
    stale_changes,
    validate_speed_keys,
)


def test_first_run_creates_default(tmp_path):
    s = ProfileStore(tmp_path)
    assert s.names() == ["Default"] and s.active().name == "Default"


def test_round_trip_keeps_int_segments(tmp_path):
    s = ProfileStore(tmp_path)
    p = s.active()
    p.changes[("towers", "archers", "price", 1)] = 7
    s.save(p)
    reloaded = ProfileStore(tmp_path).active().changes
    assert reloaded == {("towers", "archers", "price", 1): 7}
    (key,) = reloaded
    assert isinstance(key[3], int) and isinstance(reloaded[key], int)


def test_json_format(tmp_path):
    s = ProfileStore(tmp_path)
    p = s.create("Easy mode")
    p.changes[("towers", "archers", "price", 1)] = 7
    p.unlock_tower_levels = True
    p.extra_hero_points = 5
    s.save(p)
    data = json.loads((tmp_path / "easy-mode.json").read_text(encoding="utf-8"))
    assert data == {
        "version": 1,
        "name": "Easy mode",
        "changes": [{"path": ["towers", "archers", "price", 1], "value": 7}],
        "rules": {
            "unlock_tower_levels": True,
            "unlock_heroes": False,
            "unlock_towers": False,
            "unlock_spells": False,
            "allow_both_paths": False,
            "extra_hero_points": 5,
            "extra_spell_points": 0,
            "extra_upgrade_points": 0,
        },
        "live": {"speed": 1, "enemy_mult": 1.0, "troop_delta": 0, "group_gap": 100},
        "speed_keys": ["f5", "f6", "f7"],
    }


def test_profile_saved_before_hero_rules_loads_with_defaults(tmp_path):
    (tmp_path / "old.json").write_text(
        json.dumps({"version": 1, "name": "Old", "rules": {"unlock_tower_levels": True}}),
        encoding="utf-8",
    )
    s = ProfileStore(tmp_path)
    s.switch("Old")
    p = s.active()
    assert (
        p.unlock_tower_levels, p.unlock_heroes, p.unlock_towers, p.unlock_spells, p.allow_both_paths,
        p.extra_hero_points, p.extra_spell_points, p.extra_upgrade_points,
    ) == (True, False, False, False, False, 0, 0, 0)


@pytest.mark.parametrize(
    "rules",
    [
        {"extra_hero_points": -1},
        {"extra_upgrade_points": 1000},
        {"extra_spell_points": 2.5},
        {"extra_hero_points": True},
        {"unlock_heroes": 1},
    ],
)
def test_invalid_hero_rules_are_rejected(tmp_path, rules):
    s = ProfileStore(tmp_path)
    p = s.active()
    for name, value in rules.items():
        setattr(p, name, value)
    with pytest.raises(ProfileError):
        s.save(p)


def test_create_duplicate_rename_switch(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    s.duplicate("Easy", "Hard")
    s.rename("Hard", "Brutal")
    s.switch("Brutal")
    assert ProfileStore(tmp_path).active().name == "Brutal"
    with pytest.raises(ProfileError):
        s.create("easy")
    with pytest.raises(ProfileError):
        s.create("  ")


def test_duplicate_copies_content_independently(tmp_path):
    s = ProfileStore(tmp_path)
    src = s.create("A")
    src.changes[("x", 1)] = 2.5
    src.live = LiveSettings(2, 3.0, 3)
    s.save(src)
    dup = s.duplicate("A", "B")
    assert dup.changes == src.changes and dup.live == src.live
    dup.changes[("x", 1)] = 9
    assert src.changes[("x", 1)] == 2.5


def test_rename_moves_file_and_keeps_active(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    s.switch("Easy")
    s.rename("Easy", "Casual")
    assert (tmp_path / "casual.json").exists() and not (tmp_path / "easy.json").exists()
    s2 = ProfileStore(tmp_path)
    assert s2.active().name == "Casual" and s2.names() == ["Casual", "Default"]


def test_rename_collision_rejected(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("A")
    with pytest.raises(ProfileError):
        s.rename("A", "default")
    s.rename("A", "a")  # case-only change of itself is fine
    assert "a" in s.names()


def test_slug_collision_rejected(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("a b")
    with pytest.raises(ProfileError):
        s.create("a-b")
    assert s.names() == ["a b", "Default"]


def test_delete_active_and_last(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    s.switch("Easy")
    s.delete("Easy")
    assert s.active().name == "Default"
    s.delete("Default")
    assert s.names() == ["Default"]
    assert ProfileStore(tmp_path).active().name == "Default"


def test_delete_active_switches_to_first_remaining(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("Beta")
    s.create("Alpha")
    s.switch("Default")
    s.delete("Default")
    assert s.active().name == "Alpha"
    assert ProfileStore(tmp_path).active().name == "Alpha"


def test_corrupt_profile_skipped(tmp_path):
    (tmp_path / "broken.json").write_text("{nope")
    s = ProfileStore(tmp_path)
    assert "broken.json" in s.load_warnings[0] and s.active().name == "Default"


def test_invalid_content_skipped(tmp_path):
    (tmp_path / "bad.json").write_text(
        json.dumps({"version": 1, "name": "Bad", "changes": [{"path": ["a"], "value": "x"}]})
    )
    s = ProfileStore(tmp_path)
    assert "bad.json" in s.load_warnings[0] and "Bad" not in s.names()


def test_active_file_is_not_a_profile(tmp_path):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    s.switch("Easy")
    s2 = ProfileStore(tmp_path)
    assert s2.load_warnings == [] and s2.names() == ["Default", "Easy"]


def test_unknown_active_falls_back(tmp_path):
    ProfileStore(tmp_path)
    (tmp_path / "_active.json").write_text(json.dumps({"active": "Nope"}))
    assert ProfileStore(tmp_path).active().name == "Default"


def test_unknown_profile_errors(tmp_path):
    s = ProfileStore(tmp_path)
    for call in (lambda: s.switch("x"), lambda: s.delete("x"), lambda: s.rename("x", "y")):
        with pytest.raises(ProfileError):
            call()


def test_atomic_save_uses_replace_and_leaves_no_temp(tmp_path, monkeypatch):
    s = ProfileStore(tmp_path)
    calls = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (calls.append((a, b)), real(a, b))[1])
    p = s.active()
    p.changes[("a", 1)] = 3
    s.save(p)
    assert calls and calls[0][1] == tmp_path / "default.json"
    assert os.path.dirname(calls[0][0]) == str(tmp_path)
    assert sorted(f.name for f in tmp_path.iterdir()) == ["_active.json", "default.json"]


def test_failed_save_keeps_old_file(tmp_path, monkeypatch):
    s = ProfileStore(tmp_path)
    p = s.active()
    p.changes[("a", 1)] = 3
    s.save(p)
    before = (tmp_path / "default.json").read_text()
    p.changes[("a", 1)] = 4
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        s.save(p)
    assert (tmp_path / "default.json").read_text() == before
    assert [f.name for f in tmp_path.glob("*.tmp")] == []


def test_save_rejects_invalid(tmp_path):
    s = ProfileStore(tmp_path)
    p = s.active()
    p.changes[("a", 1)] = float("nan")
    with pytest.raises(ProfileError):
        s.save(p)
    p.changes.clear()
    p.speed_keys = ("f1", "f6", "f7")
    with pytest.raises(ProfileError):
        s.save(p)


def test_speed_keys_validation():
    assert validate_speed_keys(["f5", "f6", "f7"]) == ("f5", "f6", "f7")
    for bad in (["f1", "f6", "f7"], ["f5", "f5", "f7"], ["space", "f6", "f7"], ["f5", "f6"]):
        with pytest.raises(ProfileError):
            validate_speed_keys(bad)


def test_live_validation():
    LiveSettings(3, 0.25, -10).validate()
    LiveSettings(1, 10.0, 10).validate()
    LiveSettings(2, 7, 0).validate()
    LiveSettings().validate()
    for bad in (
        LiveSettings(4),
        LiveSettings(enemy_mult=0.5),
        LiveSettings(enemy_mult=1.5),
        LiveSettings(enemy_mult=101),
        LiveSettings(enemy_mult=0),
        LiveSettings(speed=True),
        LiveSettings(enemy_mult=float("nan")),
        LiveSettings(enemy_mult=True),
        LiveSettings(troop_delta=101),
        LiveSettings(troop_delta=-11),
        LiveSettings(troop_delta=1.5),
        LiveSettings(troop_delta=2.0),
        LiveSettings(troop_delta=True),
        LiveSettings(troop_delta="2"),
        LiveSettings(group_gap=9),
        LiveSettings(group_gap=501),
        LiveSettings(group_gap=50.5),
        LiveSettings(group_gap=True),
    ):
        with pytest.raises(ProfileError):
            bad.validate()


@pytest.mark.parametrize(
    "stored, enemy, troop",
    [
        ({"enemy_mult": 1.5, "troop_delta": 2}, 2.0, 2),  # a tie snaps up
        ({"enemy_mult": 0.75, "troop_delta": -3}, 1.0, -3),  # an old slider value
        ({"enemy_mult": 0.3, "troop_delta": 999}, 0.25, 100),
        ({"enemy_mult": 40, "troop_delta": -99}, 40.0, -10),
        ({"enemy_mult": 250, "troop_delta": 0}, 100.0, 0),
        ({"enemy_mult": 3.0, "troop_delta": 1.5}, 3.0, 2),
        ({"enemy_mult": 1.0, "troop_mult": 2.5}, 1.0, 0),  # legacy troop_mult is dropped
    ],
)
def test_load_snaps_and_clamps_live(tmp_path, stored, enemy, troop):
    _write_profile_json(tmp_path / "x.json", live={"speed": 2, **stored})
    live = ProfileStore(tmp_path).active().live
    assert live == LiveSettings(2, enemy, troop)
    assert isinstance(live.troop_delta, int)


@pytest.mark.parametrize("stored, gap", [(None, 100), (50, 50), (999, 500), (3, 10), (62.5, 63)])
def test_load_group_gap_defaults_and_clamps(tmp_path, stored, gap):
    # a profile from before the Gaps box has none: the game's own gaps (100%)
    live = {"speed": 1} if stored is None else {"speed": 1, "group_gap": stored}
    _write_profile_json(tmp_path / "x.json", live=live)
    assert ProfileStore(tmp_path).active().live.group_gap == gap


def test_legacy_troop_mult_not_saved_again(tmp_path):
    _write_profile_json(
        tmp_path / "x.json", live={"speed": 1, "enemy_mult": 2.0, "troop_mult": 2.0}
    )
    s = ProfileStore(tmp_path)
    s.save(s.active())
    data = json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))
    assert data["live"] == {"speed": 1, "enemy_mult": 2.0, "troop_delta": 0, "group_gap": 100}


@pytest.mark.parametrize(
    "live", [{"enemy_mult": "2"}, {"troop_delta": "2"}, {"enemy_mult": None}, {"troop_delta": True}, {"enemy_mult": False}]
)
def test_wrong_typed_live_values_skipped(tmp_path, live):
    _write_profile_json(tmp_path / "bad.json", live=live)
    s = ProfileStore(tmp_path)
    assert "bad.json" in s.load_warnings[0] and s.names() == ["Default"]


def test_stale(tree, tmp_path):
    p = ProfileStore(tmp_path).active()
    p.changes = {("towers", "archers", "price", 1): 7, ("towers", "gone", 1): 1}
    assert stale_changes(p, tree) == [("towers", "gone", 1)]


def test_stale_enum_and_non_numeric(tree):
    enum_leaf = next(leaf for leaf in tree.leaves.values() if leaf.is_enum)
    str_leaf = next(leaf for leaf in tree.leaves.values() if leaf.kind == "str")
    p = Profile("x", changes={enum_leaf.path: 1, str_leaf.path: 1})
    assert stale_changes(p, tree) == [enum_leaf.path, str_leaf.path]


def _write_profile_json(path, **over):
    data = {"version": 1, "name": "X", "changes": []}
    data.update(over)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_corrupt_default_only(tmp_path):
    (tmp_path / "default.json").write_text("{nope")
    s = ProfileStore(tmp_path)
    assert s.names() == ["Default"] and s.active().name == "Default"
    assert "default.json" in s.load_warnings[0]
    assert (tmp_path / "default.json").read_text() == "{nope"  # user's file untouched
    s2 = ProfileStore(tmp_path)
    assert s2.names() == ["Default"] and s2.active().name == "Default"


def test_delete_last_with_corrupt_default_present(tmp_path):
    _write_profile_json(tmp_path / "easy.json", name="Easy")
    (tmp_path / "default.json").write_text("{nope")
    s = ProfileStore(tmp_path)
    assert s.names() == ["Easy"]
    s.switch("Easy")
    s.delete("Easy")
    assert s.names() == ["Default"] and s.active().name == "Default"
    assert not (tmp_path / "easy.json").exists()
    s2 = ProfileStore(tmp_path)
    assert s2.names() == ["Default"] and s2.active().name == "Default"


@pytest.mark.parametrize(
    "bad_path", [[["a"], 1], [{"a": 1}], [None], [True], [1.5], []]
)
def test_bad_path_shapes_skipped(tmp_path, bad_path):
    _write_profile_json(tmp_path / "bad.json", changes=[{"path": bad_path, "value": 1}])
    s = ProfileStore(tmp_path)
    assert "bad.json" in s.load_warnings[0] and s.names() == ["Default"]


def test_huge_int_value_skipped(tmp_path):
    (tmp_path / "huge.json").write_text(
        '{"version": 1, "name": "Huge", "changes": [{"path": ["a"], "value": 1' + "0" * 400 + "}]}"
    )
    s = ProfileStore(tmp_path)
    assert "huge.json" in s.load_warnings[0] and s.names() == ["Default"]


def test_huge_int_mult_skipped(tmp_path):
    (tmp_path / "huge.json").write_text(
        '{"version": 1, "name": "Huge", "live": {"enemy_mult": 1' + "0" * 400 + "}}"
    )
    s = ProfileStore(tmp_path)
    assert "huge.json" in s.load_warnings[0] and s.names() == ["Default"]
    with pytest.raises(ProfileError):
        LiveSettings(troop_delta=10**400).validate()


def test_speed_keys_must_be_love_names():
    assert validate_speed_keys(["a", "-", "kp1"]) == ("a", "-", "kp1")
    assert validate_speed_keys(["F5", "pageup", "`"]) == ("f5", "pageup", "`")
    for bad in (["banana", "f6", "f7"], ["ctrl+f5", "f6", "f7"], ["f5", "f6", "f20"], ["f5", "f6", ""]):
        with pytest.raises(ProfileError):
            validate_speed_keys(bad)


def _locked_unlink(monkeypatch, target_name):
    from pathlib import Path

    real = Path.unlink

    def fake(self, *a, **kw):
        if self.name == target_name:
            raise PermissionError("locked")
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", fake)


def test_delete_unlink_failure_keeps_profile(tmp_path, monkeypatch):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    _locked_unlink(monkeypatch, "easy.json")
    with pytest.raises(ProfileError):
        s.delete("Easy")
    assert s.names() == ["Default", "Easy"]
    assert ProfileStore(tmp_path).names() == ["Default", "Easy"]


def test_delete_last_unlink_failure_leaves_store_intact(tmp_path, monkeypatch):
    _write_profile_json(tmp_path / "easy.json", name="Easy")
    s = ProfileStore(tmp_path)
    s.create("Other")
    s.delete("Other")
    _locked_unlink(monkeypatch, "easy.json")
    with pytest.raises(ProfileError):
        s.delete("Easy")
    assert s.names() == ["Easy"] and s.active().name == "Easy"
    assert sorted(f.name for f in tmp_path.glob("*.json")) == ["_active.json", "easy.json"]


def test_rename_unlink_failure_keeps_old_name(tmp_path, monkeypatch):
    s = ProfileStore(tmp_path)
    s.create("Easy")
    _locked_unlink(monkeypatch, "easy.json")
    with pytest.raises(ProfileError):
        s.rename("Easy", "Casual")
    assert s.names() == ["Default", "Easy"]
    assert not (tmp_path / "casual.json").exists()
    assert ProfileStore(tmp_path).names() == ["Default", "Easy"]
