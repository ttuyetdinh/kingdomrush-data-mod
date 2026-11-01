import time

import pytest

from krmod.model.grouping import GroupIndex, place


def test_every_number_has_one_home(tree):
    sc = GroupIndex.build(tree).self_check()
    assert (sc.total, sc.placed, sc.unplaced) == (5857, 5857, [])


def test_tower_and_skill_placement():
    p = place(("towers", "archers", "price", 1))
    assert p.home.id == "towers/archers" and p.extra == ()
    p = place(("towers", "knights", "skill_a", "cooldown", 1))
    assert p.home.id == "towers/knights"
    assert [c.id for c in p.extra] == ["skills/towers/knights"]


def test_troops_and_specials():
    assert place(("towers", "knights", "soldier", "hp_max", 1)).home.tab == "Troops"
    assert place(("specials", "towers", "stage_07_barn", "soldier", "hp_max")).home.tab == "Troops"
    assert place(("powers", "reinforcements", "special_soldier", "hp_max")).home.tab == "Troops"
    assert (
        place(("specials", "towers", "stage_07_barn", "max_soldiers")).home.id
        == "stages/towers/stage_07_barn"
    )


def test_heroes_spells_enemies():
    assert place(("heroes", "hero_bolin", "stats", "hp")).home.id == "heroes/hero_bolin"
    assert place(("upgrades", "power_rain_of_fire", "x")).home.id == "skills/powers/rain_of_fire"
    e = place(("enemies", "demons", "demon_lord", "hp"))
    assert (e.home.id, e.home.group) == ("enemies/demons/demon_lord", "Demons")
    assert place(("enemies", "jt_boss", "hp")).home.group == "Bosses"


def test_unknown_goes_to_other():
    assert place(("kr1_mode", "mystery", 1)).home.id == "other/Towers"


def test_titles_and_groups():
    assert place(("towers", "archers", "price", 1)).home.title == "Archers"
    assert place(("towers", "archers", "price", 1)).home.group == "Towers"
    assert place(("towers", "knights", "price", 1)).home.title == "Knights"
    assert place(("towers", "common", "x")).home.title == "Common"
    assert place(("towers", "upgrades", "x", "y")).home.title == "Tower upgrades"
    k = place(("kr1_mode", "towers", "barracks", "price", 1)).home
    assert (k.id, k.title, k.group) == ("towers/kr1/barracks", "Classic Barracks", "Classic towers")
    h = place(("heroes", "hero_bolin", "stats", "hp")).home
    assert (h.title, h.group, h.tab) == ("Bolin", "Heroes", "Heroes")
    d = place(("enemies", "demons", "demon_lord", "hp", 1)).home
    assert d.title == "Demon lord"
    sk = place(("heroes", "hero_bolin", "skill_a", "cooldown", 1))
    assert sk.extra[0].tab == "Skills" and sk.extra[0].title == "Bolin"
    t = place(("towers", "knights", "soldier", "hp_max", 1)).home
    assert (t.id, t.title, t.group) == ("troops/towers.knights.soldier", "Knights soldier", "Towers")
    t = place(("kr1_mode", "towers", "barracks", "soldier", "hp")).home
    assert (t.title, t.group) == ("Classic Barracks soldier", "Classic towers")
    t = place(("powers", "reinforcements", "special_soldier", "hp_max")).home
    assert (t.title, t.group) == ("Reinforcements special soldier", "Spells")
    assert place(("kr1_mode", "upgrades", "archers", "x", "y")).home.title == "Classic upgrades"
    assert place(("specials", "stage_01", "king", "x")).home.id == "stages/stage_01"
    assert place(("items", "gold", "gold")).home.id == "items/gold"


def test_prefix_is_a_leading_path_of_each_leaf(tree):
    idx = GroupIndex.build(tree)
    for p in tree.leaves:
        pl = idx.placement(p)
        for card in (pl.home, *pl.extra):
            if card.prefix and not (card.id.startswith("skills/powers/") and p[0] == "upgrades"):
                assert p[: len(card.prefix)] == card.prefix, (p, card)


def test_cards_listing_and_paths(tree):
    idx = GroupIndex.build(tree)
    titles = [c.title for c in idx.cards("Towers")]
    assert "Archers" in titles and "Knights" in titles
    assert "Demon lord" in [c.title for c in idx.cards("Enemies")]
    paths = idx.paths_of("towers/knights")
    assert paths == sorted(paths, key=lambda p: tuple((isinstance(s, str), s if isinstance(s, str) else "", s if isinstance(s, int) else 0) for s in p))
    assert ("towers", "knights", "skill_a", "price", 1) in idx.paths_of("skills/towers/knights")
    assert ("towers", "knights", "skill_a", "price", 1) in paths
    assert idx.card("towers/archers").prefix == ("towers", "archers")


def test_build_is_fast(tree):
    start = time.perf_counter()
    GroupIndex.build(tree)
    assert time.perf_counter() - start < 1.0
