import dataclasses

import pytest
from PIL import Image

from krmod.assets import portraits
from krmod.assets.portraits import build_portrait_cache, portrait_for


@pytest.fixture(scope="module")
def cache_paths(game_paths, tmp_path_factory):
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path_factory.mktemp("cache"))
    written = build_portrait_cache(paths)
    return paths, written


def test_cache_entries_are_valid_pngs(cache_paths):
    paths, written = cache_paths
    files = list((paths.cache_dir / "portraits").glob("*.png"))
    assert written > 0
    assert len(files) == written
    for f in files:
        with Image.open(f) as im:
            assert min(im.size) >= 32
            assert max(im.size) <= 256


def test_unknown_card_has_no_portrait(tmp_path):
    assert portrait_for("stages/stage_99", tmp_path) is None


def test_portrait_for_reads_cache_by_flattened_id(cache_paths):
    paths, _ = cache_paths
    found = portrait_for("towers/archers", paths.cache_dir)
    assert found == paths.cache_dir / "portraits" / "towers__archers.png"
    assert found.is_file()


def test_every_tower_hero_and_power_has_a_portrait(cache_paths, tree):
    paths, _ = cache_paths
    ids = []
    ids += [f"towers/{k}" for k in {p[1] for p in tree.leaves if p[0] == "towers"} if k != "upgrades"]
    ids += [f"heroes/{k}" for k in {p[1] for p in tree.leaves if p[0] == "heroes"} if str(k).startswith("hero_")]
    ids += [f"skills/powers/{k}" for k in {p[1] for p in tree.leaves if p[0] == "powers"}]
    missing = [i for i in ids if portrait_for(i, paths.cache_dir) is None]
    assert not missing
    assert len(ids) == 15 + 12 + 9


def test_most_enemies_have_a_portrait(cache_paths, tree):
    paths, _ = cache_paths
    pairs = {(p[1], p[2]) for p in tree.leaves if p[0] == "enemies" and len(p) > 3}
    ids = [f"enemies/{f}/{e}" for f, e in pairs]
    hit = [i for i in ids if portrait_for(i, paths.cache_dir) is not None]
    assert len(hit) >= 50
    assert portrait_for("enemies/demons/demon_lord", paths.cache_dir) is not None
    assert portrait_for("enemies/jt_boss", paths.cache_dir) is not None
    assert portrait_for("enemies/dark_army/death_rider", paths.cache_dir) is not None


def test_second_build_skips_existing_files(cache_paths):
    paths, written = cache_paths
    stamp = {f: f.stat().st_mtime_ns for f in (paths.cache_dir / "portraits").glob("*.png")}
    assert build_portrait_cache(paths) == 0
    after = {f: f.stat().st_mtime_ns for f in (paths.cache_dir / "portraits").glob("*.png")}
    assert stamp == after


def test_missing_descriptor_only_loses_its_family(game_paths, tmp_path, monkeypatch):
    monkeypatch.setitem(portraits._DESCRIPTORS, "encyclopedia_thumbs", "no_such_descriptor.lua")
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path)
    assert build_portrait_cache(paths) > 0
    assert portrait_for("towers/archers", tmp_path) is not None
    assert portrait_for("enemies/demons/demon_lord", tmp_path) is not None
    assert portrait_for("enemies/dark_army/death_rider", tmp_path) is None


def test_missing_big_descriptor_keeps_hud_families(game_paths, tmp_path, monkeypatch):
    monkeypatch.setitem(portraits._DESCRIPTORS, "room_tower", "no_such_descriptor.lua")
    paths = dataclasses.replace(game_paths, cache_dir=tmp_path)
    assert build_portrait_cache(paths) > 0
    assert portrait_for("towers/archers", tmp_path) is None
    assert portrait_for("enemies/demons/demon_lord", tmp_path) is not None
    assert portrait_for("towers/kr1/tesla", tmp_path) is not None


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
    assert len(list((tmp_path / "portraits").glob("*.png"))) == written


def test_unreadable_exe_returns_zero(game_paths, tmp_path):
    paths = dataclasses.replace(game_paths, exe=tmp_path / "missing.exe", cache_dir=tmp_path)
    assert build_portrait_cache(paths) == 0
