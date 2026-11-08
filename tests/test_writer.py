import dataclasses
from pathlib import Path
import pytest

from krmod.model.values import BalanceTree
from krmod.modgen.writer import (
    LAUNCH_BAT,
    ApplyResult,
    apply_mod,
    atomic_write,
    data_table,
    write_live,
)
from krmod.profiles import LiveSettings, Profile, ProfileError


@pytest.fixture
def tmp_game(game_paths, tmp_path):
    exe = tmp_path / "Kingdom Rush Genesis.exe"
    exe.write_text("")
    mods_dir = tmp_path / "mods"
    return dataclasses.replace(
        game_paths,
        game_dir=tmp_path,
        exe=exe,
        mods_dir=mods_dir,
    )


def test_apply_writes_everything(tmp_game, tree):
    orig2 = tree.leaves[("towers", "archers", "price", 2)].value
    p = Profile(
        name="T",
        changes={
            ("towers", "archers", "price", 1): 7,
            ("towers", "gone", 1): 1,
            ("towers", "archers", "price", 2): orig2,
        },
        live=LiveSettings(),
    )
    r = apply_mod(tmp_game, p, tree)
    names = {f.relative_to(tmp_game.mods_dir).as_posix() for f in r.files}
    assert {
        "kr_mod.lua",
        "kr_mod/stats.lua",
        "kr_mod_data.lua",
        "kr_mod_live.lua",
        "launch_modded.bat",
    } <= names
    assert (r.applied, r.stale) == (1, [("towers", "gone", 1)])
    assert not list(tmp_game.mods_dir.glob("*.tmp"))
    assert (tmp_game.mods_dir / "launch_modded.bat").read_bytes() == LAUNCH_BAT.encode("utf-8")
    src_stats = tmp_game.mod_template_dir / "kr_mod" / "stats.lua"
    dst_stats = tmp_game.mods_dir / "kr_mod" / "stats.lua"
    assert dst_stats.read_bytes() == src_stats.read_bytes()


def test_data_file_loads_in_lua(tmp_game, tree, lua):
    apply_mod(
        tmp_game,
        Profile(
            name="T",
            changes={("towers", "archers", "price", 1): 7},
            live=LiveSettings(),
        ),
        tree,
    )
    src = (tmp_game.mods_dir / "kr_mod_data.lua").read_text()
    lua.run(f"D = (function() {src} end)()")
    assert (
        lua.run(
            "return D.changes[1].p[4] .. ':' .. D.changes[1].v", want_result=True
        )
        == b"1:7"
    )


def test_live_file(tmp_game):
    write_live(tmp_game, LiveSettings(2, 1.5, 3.0))
    assert (
        (tmp_game.mods_dir / "kr_mod_live.lua").read_bytes()
        == b"return { speed = 2, enemy_mult = 1.5, troop_mult = 3.0 }\n"
    )
    assert (
        (tmp_game.mods_dir / "kr_mod_live.lua").read_text().strip()
        == "return { speed = 2, enemy_mult = 1.5, troop_mult = 3.0 }"
    )


def test_live_file_validates(tmp_game):
    with pytest.raises(ProfileError):
        write_live(tmp_game, LiveSettings(speed=4))
    assert not (tmp_game.mods_dir / "kr_mod_live.lua").exists()


def test_data_table_speed_keys_normalized(tree):
    p = Profile(
        name="T",
        changes={},
        speed_keys=("F5", "  F6  ", "F7"),
        unlock_tower_levels=True,
    )
    dt = data_table(p, tree)
    assert dt["speed_keys"] == ["f5", "f6", "f7"]
    assert dt["rules"] == {"unlock_tower_levels": True}
    assert dt["version"] == 1


def test_atomic_write_retries_and_cleans_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "sub" / "target.txt"
    attempts = 0

    def fail_replace(src, dst):
        nonlocal attempts
        attempts += 1
        raise PermissionError("locked")

    monkeypatch.setattr("os.replace", fail_replace)
    with pytest.raises(PermissionError):
        atomic_write(target, "hello", retries=3)

    assert attempts == 3
    assert not list(tmp_path.rglob("*.tmp"))
    assert not target.exists()


def test_atomic_write_byte_exact(tmp_path):
    target = tmp_path / "test.txt"
    atomic_write(target, "data")
    assert target.read_bytes() == b"data"

    target_lf = tmp_path / "lf.txt"
    atomic_write(target_lf, "line1\nline2\n")
    assert target_lf.read_bytes() == b"line1\nline2\n"

    target_crlf = tmp_path / "crlf.txt"
    atomic_write(target_crlf, "line1\r\nline2\r\n")
    assert target_crlf.read_bytes() == b"line1\r\nline2\r\n"

    assert not list(tmp_path.glob("*.tmp"))


def test_launch_bat_constant():
    assert '@echo off' in LAUNCH_BAT
    assert 'Kingdom Rush Genesis.exe' in LAUNCH_BAT
    assert '-balance_override mods.kr_mod' in LAUNCH_BAT


def test_apply_mod_copies_dynamically_added_template_modules(tmp_game, tree, tmp_path):
    custom_template = tmp_path / "custom_template"
    custom_template.mkdir()
    (custom_template / "kr_mod.lua").write_text("-- main\n", encoding="utf-8")
    mod_sub = custom_template / "kr_mod"
    mod_sub.mkdir()
    (mod_sub / "stats.lua").write_text("-- stats\n", encoding="utf-8")
    (mod_sub / "live.lua").write_text("-- live\n", encoding="utf-8")
    (mod_sub / "nested").mkdir()
    (mod_sub / "nested" / "extra.lua").write_text("-- extra\n", encoding="utf-8")

    game = dataclasses.replace(tmp_game, mod_template_dir=custom_template)
    r = apply_mod(game, Profile(name="T", changes={}, live=LiveSettings()), tree)
    rel_names = {f.relative_to(game.mods_dir).as_posix() for f in r.files}
    assert "kr_mod.lua" in rel_names
    assert "kr_mod/stats.lua" in rel_names
    assert "kr_mod/live.lua" in rel_names
    assert "kr_mod/nested/extra.lua" in rel_names
    assert (game.mods_dir / "kr_mod" / "nested" / "extra.lua").read_text() == "-- extra\n"


def test_live_seq_only_bumps_on_request(tmp_game):
    live_file = tmp_game.mods_dir / "kr_mod_live.lua"
    write_live(tmp_game, LiveSettings(1, 1.0, 1.0))
    assert "seq" not in live_file.read_text()

    write_live(tmp_game, LiveSettings(1, 1.0, 1.0), bump_seq=True)
    first = int(live_file.read_text().split("seq = ")[1].split(" ")[0])
    write_live(tmp_game, LiveSettings(1, 2.0, 1.0))
    assert f"seq = {first} " in live_file.read_text()
    write_live(tmp_game, LiveSettings(1, 2.0, 1.0), bump_seq=True)
    second = int(live_file.read_text().split("seq = ")[1].split(" ")[0])
    assert second > first
