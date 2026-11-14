import dataclasses

import pytest

from krmod.gamedata.names import GameNames, read_game_names, tidy
from krmod.gameload import load_game
from krmod.model.grouping_rules import TABS


@pytest.mark.parametrize("raw, shown", [
    ("ARCHER GARRISON", "Archer Garrison"),
    ("WRATH OF THE FOREST", "Wrath of the Forest"),
    ("GNOME'S SHOP", "Gnome's Shop"),
    ("500MM BIG BERTHA", "500MM Big Bertha"),
    ("TESLA X104", "Tesla X104"),
    ("POISON-TIP ARROW", "Poison-Tip Arrow"),
    ("1. LINIREAN CASTLE", "1. Linirean Castle"),
    ("J.T.", "J.T."),
    ("Rain of Fire", "Rain of Fire"),  # already mixed case: kept
])
def test_tidy(raw, shown):
    assert tidy(raw) == shown


@pytest.fixture(scope="module")
def names(game_paths):
    return read_game_names(game_paths)


@pytest.mark.parametrize("card_id, name", [
    ("towers/archers", "Archer Garrison"),
    ("towers/light_priestess", "Light Priestess"),
    ("towers/sunray_master", "Sunray Master"),
    ("towers/kr1/archers", "Archer Tower"),
    ("towers/kr1/ranger", "Rangers Hideout"),
    ("heroes/hero_myriath", "Gemina"),
    ("spells/soaring_shop", "Gnome's Shop"),
    ("enemies/jt_boss", "J.T."),
    ("enemies/dark_army/skeleton_big", "Bone Golem"),
    ("items/bomb", "Fat Boy"),
    ("stages/stage_01", "1. Linirean Castle"),
    ("stages/towers/stage_11_tower_camp", "Linirean Encampment"),
    ("troops/towers.knights.soldier", "Knights Order soldier"),
    ("troops/towers.alchemist.skill_b.soldier", "Bob"),
])
def test_card_names_match_the_game(names, card_id, name):
    assert names.card_name(card_id) == name


@pytest.mark.parametrize("card_id, group, name", [
    ("towers/archers", "skill_a", "Spot Weakness"),
    ("towers/archers", "ultimate", "Arrow Frenzy"),
    ("towers/light_priestess", "skill_c", "Panacea"),
    ("towers/kr1/barbarians", "dual", "More Axes"),
    ("heroes/hero_bolin", "skill_a", "Smoke Mortar"),
    ("heroes/hero_bolin", "talent_2", "Explosive Rounds"),
    ("heroes/hero_bolin", "ultimate", "Suppressive Fire"),
    ("spells/rain_of_fire", "upgrades.l2a", "Hasty Spellcasting"),
])
def test_section_names_match_the_game(names, card_id, group, name):
    assert names.section_name(card_id, group) == name


def test_sub_sections_and_plain_sections_have_no_game_name(names):
    assert names.section_name("towers/archers", "basic_attack") is None
    assert names.section_name("towers/archers", "ultimate.burn") is None


def test_every_unit_card_gets_a_game_name(names, game_paths):
    _, index = load_game(game_paths)
    unnamed = [
        c.id for tab in TABS for c in index.cards(tab) if names.card_name(c.id) is None
    ]
    # cards the game has no single name for
    assert sorted(unnamed) == sorted([
        "towers/upgrades", "towers/kr1_upgrades", "heroes/common", "enemies/all",
        "enemies/dark_army/exalted_crow", "enemies/dark_army/skeleton_goat",
        "troops/specials.stage_06.nivus.books.soldier",
        "troops/specials.towers.stage_17_paladin_barracks.soldier",
        "stages/towers/stage_16_treant_attacker", "stages/towers/stage_16_treant_healer",
        "stages/towers/stage_16_treant_killer", "stages/towers/stage_16_treant_rooter",
        "stages/towers/stage_17_paladin_barracks",
        "stages/terrain_1", "stages/terrain_2", "stages/terrain_3",
    ])


def test_loaded_index_uses_game_names(game_paths):
    _, index = load_game(game_paths)
    assert index.card("towers/archers").title == "Archer Garrison"
    assert index.card_of(("towers", "archers", "price", 1)).title == "Archer Garrison"
    assert index.card("towers/upgrades").title == "Tower upgrades"  # no game name: kept
    assert index.section_name("towers/archers", "skill_a") == "Spot Weakness"
    titles = [c.title for c in index.cards("Towers") if c.group == "Towers"]
    assert titles == sorted(titles)


def test_unreadable_exe_keeps_the_apps_titles(game_paths, tmp_path):
    paths = dataclasses.replace(game_paths, exe=tmp_path / "missing.exe")
    names = read_game_names(paths)
    assert names == GameNames()
    assert names.card_name("towers/archers") is None
