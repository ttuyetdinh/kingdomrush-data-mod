import dataclasses

import pytest
from PIL import Image

from krmod.assets import portraits
from krmod.assets.portraits import build_portrait_cache, portrait_for
from krmod.paths import GamePaths


@pytest.fixture(scope="module")
def cache_paths(game_paths, tmp_path_factory):
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path_factory.mktemp("cache"))
    written = build_portrait_cache(paths)
    return paths, written


def test_cache_entries_are_valid_pngs(cache_paths):
    paths, written = cache_paths
    files = list((paths.portraits_dir).glob("*.png"))
    assert written > 0
    assert len(files) == written
    for f in files:
        with Image.open(f) as im:
            assert min(im.size) >= 32
            assert max(im.size) <= 256


def test_unknown_card_has_no_portrait(tmp_path):
    assert portrait_for("stages/stage_99", tmp_path / "portraits") is None


def test_portrait_for_reads_cache_by_flattened_id(cache_paths):
    paths, _ = cache_paths
    found = portrait_for("towers/archers", paths.portraits_dir)
    assert found == paths.portraits_dir / "towers__archers.png"
    assert found.is_file()


def test_every_tower_hero_and_power_has_a_portrait(cache_paths, tree):
    paths, _ = cache_paths
    ids = []
    ids += [f"towers/{k}" for k in {p[1] for p in tree.leaves if p[0] == "towers"} if k != "upgrades"]
    ids += [f"heroes/{k}" for k in {p[1] for p in tree.leaves if p[0] == "heroes"} if str(k).startswith("hero_")]
    ids += [f"spells/{k}" for k in {p[1] for p in tree.leaves if p[0] == "powers"}]
    missing = [i for i in ids if portrait_for(i, paths.portraits_dir) is None]
    assert not missing
    assert len(ids) == 15 + 12 + 9


def test_every_troop_item_and_classic_tower_has_a_portrait(cache_paths, game_paths):
    from krmod.gameload import load_game

    paths, _ = cache_paths
    _, idx = load_game(game_paths)
    ids = [c.id for tab in ("Troops", "Items") for c in idx.cards(tab)]
    ids += [c.id for c in idx.cards("Towers") if c.id.startswith("towers/kr1/")]
    missing = [i for i in ids if portrait_for(i, paths.portraits_dir) is None]
    assert not missing
    assert len(ids) >= 26 + 3 + 12


def test_stage_towers_and_heroes_have_portraits_except_the_tavern(cache_paths, game_paths):
    from krmod.gameload import load_game

    paths, _ = cache_paths
    _, idx = load_game(game_paths)
    ids = [c.id for c in idx.cards("Stages") if c.id.startswith(("stages/towers/", "stages/heroes/"))]
    missing = [i for i in ids if portrait_for(i, paths.portraits_dir) is None]
    assert missing == ["stages/towers/stage_14_tavern"]


def test_most_enemies_have_a_portrait(cache_paths, tree):
    paths, _ = cache_paths
    pairs = {(p[1], p[2]) for p in tree.leaves if p[0] == "enemies" and len(p) > 3}
    ids = [f"enemies/{f}/{e}" for f, e in pairs]
    hit = [i for i in ids if portrait_for(i, paths.portraits_dir) is not None]
    assert len(hit) >= 50
    assert portrait_for("enemies/demons/demon_lord", paths.portraits_dir) is not None
    assert portrait_for("enemies/jt_boss", paths.portraits_dir) is not None
    assert portrait_for("enemies/dark_army/death_rider", paths.portraits_dir) is not None


def test_second_build_skips_existing_files(cache_paths):
    paths, written = cache_paths
    stamp = {f: f.stat().st_mtime_ns for f in (paths.portraits_dir).glob("*.png")}
    assert build_portrait_cache(paths) == 0
    after = {f: f.stat().st_mtime_ns for f in (paths.portraits_dir).glob("*.png")}
    assert stamp == after


def test_missing_descriptor_only_loses_its_family(game_paths, tmp_path, monkeypatch):
    monkeypatch.setitem(portraits._DESCRIPTORS, "encyclopedia_thumbs", "no_such_descriptor.lua")
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path)
    assert build_portrait_cache(paths) > 0
    assert portrait_for("towers/archers", paths.portraits_dir) is not None
    assert portrait_for("enemies/demons/demon_lord", paths.portraits_dir) is not None
    assert portrait_for("enemies/dark_army/death_rider", paths.portraits_dir) is None


def test_missing_big_descriptor_keeps_hud_families(game_paths, tmp_path, monkeypatch):
    monkeypatch.setitem(portraits._DESCRIPTORS, "room_tower", "no_such_descriptor.lua")
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path)
    assert build_portrait_cache(paths) > 0
    assert portrait_for("towers/archers", paths.portraits_dir) is None
    assert portrait_for("enemies/demons/demon_lord", paths.portraits_dir) is not None
    assert portrait_for("towers/kr1/tesla", paths.portraits_dir) is not None


def test_decode_failure_does_not_raise_and_skips_only_that_card(game_paths, tmp_path, monkeypatch):
    real_crop = portraits._Atlases.crop
    calls = {"n": 0}

    def flaky_crop(self, frame):
        calls["n"] += 1
        if calls["n"] == 1:
            raise NotImplementedError("unsupported DDS format")
        return real_crop(self, frame)

    monkeypatch.setattr(portraits._Atlases, "crop", flaky_crop)
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path)
    written = build_portrait_cache(paths)
    assert written > 100
    assert len(list(paths.portraits_dir.glob("*.png"))) == written


def test_unreadable_exe_returns_zero(game_paths, tmp_path):
    paths = dataclasses.replace(game_paths, exe=tmp_path / "missing.exe", cache_dir=tmp_path)
    assert build_portrait_cache(paths) == 0


def test_old_flat_cache_is_removed_but_folder_caches_stay(tmp_path):
    paths = GamePaths.for_game_dir(tmp_path / "game", tmp_path / "repo")  # no exe: nothing is built
    flat = paths.cache_dir / "portraits"
    flat.mkdir(parents=True)
    (flat / "towers__archers.png").write_bytes(b"old")
    other = flat / "0123456789ab"
    other.mkdir()
    (other / "towers__archers.png").write_bytes(b"keep")
    assert build_portrait_cache(paths) == 0
    assert not (flat / "towers__archers.png").exists()
    assert (other / "towers__archers.png").read_bytes() == b"keep"
