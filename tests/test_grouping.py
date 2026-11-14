import time

import pytest

from krmod.model.grouping import GroupIndex, place


def test_every_number_has_one_home(tree):
    sc = GroupIndex.build(tree).self_check()
    assert (sc.total, sc.placed, sc.unplaced) == (5857, 5857, [])


def test_skills_stay_in_their_owners_card():
    assert place(("towers", "archers", "price", 1)).id == "towers/archers"
    assert place(("towers", "knights", "skill_a", "cooldown", 1)).id == "towers/knights"
    assert place(("heroes", "hero_bolin", "ultimate", "cooldown", 1)).id == "heroes/hero_bolin"
    k = place(("kr1_mode", "towers", "tesla", "skill_x", "damage", 1))
    assert k.id == "towers/kr1/tesla"


def test_troops_and_specials():
    assert place(("towers", "knights", "soldier", "hp_max", 1)).tab == "Troops"
    assert place(("specials", "towers", "stage_07_barn", "soldier", "hp_max")).tab == "Troops"
    assert place(("powers", "reinforcements", "special_soldier", "hp_max")).tab == "Troops"
    assert (
        place(("specials", "towers", "stage_07_barn", "max_soldiers")).id
        == "stages/towers/stage_07_barn"
    )


def test_heroes_spells_enemies():
    assert place(("heroes", "hero_bolin", "stats", "hp")).id == "heroes/hero_bolin"
    s = place(("upgrades", "power_rain_of_fire", "x"))
    assert (s.id, s.tab) == ("spells/rain_of_fire", "Spells")
    assert place(("powers", "rain_of_fire", "damage", 1)).id == "spells/rain_of_fire"
    e = place(("enemies", "demons", "demon_lord", "hp"))
    assert (e.id, e.group) == ("enemies/demons/demon_lord", "Demons")
    assert place(("enemies", "jt_boss", "hp")).group == "Bosses"


def test_unknown_goes_to_other():
    assert place(("kr1_mode", "mystery", 1)).id == "other/Towers"


def test_titles_and_groups():
    assert place(("towers", "archers", "price", 1)).title == "Archers"
    assert place(("towers", "archers", "price", 1)).group == "Towers"
    assert place(("towers", "knights", "price", 1)).title == "Knights"
    assert place(("towers", "common", "x")).title == "Common"
    assert place(("towers", "upgrades", "x", "y")).title == "Tower upgrades"
    k = place(("kr1_mode", "towers", "barracks", "price", 1))
    assert (k.id, k.title, k.group) == ("towers/kr1/barracks", "Classic Barracks", "Classic towers")
    h = place(("heroes", "hero_bolin", "stats", "hp"))
    assert (h.title, h.group, h.tab) == ("Bolin", "Heroes", "Heroes")
    d = place(("enemies", "demons", "demon_lord", "hp", 1))
    assert d.title == "Demon lord"
    t = place(("towers", "knights", "soldier", "hp_max", 1))
    assert (t.id, t.title, t.group) == ("troops/towers.knights.soldier", "Knights soldier", "Towers")
    t = place(("kr1_mode", "towers", "barracks", "soldier", "hp"))
    assert (t.title, t.group) == ("Classic Barracks soldier", "Classic towers")
    t = place(("powers", "reinforcements", "special_soldier", "hp_max"))
    assert (t.title, t.group) == ("Reinforcements special soldier", "Spells")
    u = place(("kr1_mode", "upgrades", "archers", "x", "y"))
    assert (u.id, u.tab, u.title, u.group) == (
        "towers/kr1_upgrades", "Towers", "Classic upgrades", "Classic towers"
    )
    assert place(("specials", "stage_01", "king", "x")).id == "stages/stage_01"
    assert place(("items", "gold", "gold")).id == "items/gold"


def test_prefix_is_a_leading_path_of_each_leaf(tree):
    idx = GroupIndex.build(tree)
    for p in tree.leaves:
        card = idx.card_of(p)
        if card.prefix and not (card.id.startswith("spells/") and p[0] == "upgrades"):
            assert p[: len(card.prefix)] == card.prefix, (p, card)


def test_cards_listing_and_paths(tree):
    idx = GroupIndex.build(tree)
    titles = [c.title for c in idx.cards("Towers")]
    assert "Archers" in titles and "Knights" in titles
    assert "Demon lord" in [c.title for c in idx.cards("Enemies")]
    paths = idx.paths_of("towers/knights")
    assert paths == sorted(paths, key=lambda p: tuple((isinstance(s, str), s if isinstance(s, str) else "", s if isinstance(s, int) else 0) for s in p))
    assert ("towers", "knights", "skill_a", "price", 1) in paths
    assert "Classic upgrades" in titles
    assert [c.title for c in idx.cards("Spells")] and all(
        c.group == "Spells" for c in idx.cards("Spells")
    )
    assert idx.card("towers/archers").prefix == ("towers", "archers")


def test_build_is_fast(tree):
    start = time.perf_counter()
    GroupIndex.build(tree)
    assert time.perf_counter() - start < 1.0
