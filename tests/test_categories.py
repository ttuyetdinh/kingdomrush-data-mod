import pytest

from krmod.model.categories import CATEGORY_NAMES, category_of


@pytest.mark.parametrize("path,cat", [
    (("towers", "archers", "price", 1), "All costs"),
    (("x", "damage_min", 1), "All damage"), (("x", "damage_type"), None),
    (("x", "damage_radius"), "All range"), (("x", "cooldown", 2), "All cooldowns"),
    (("x", "cooldown_factor"), None), (("x", "hp_max", 1), "All HP"), (("x", "lives_cost"), None),
    (("x", "damage_factor"), None), (("x", "cost_factor"), None),
    (("x", "skill_cost_red_factor"), None),
    (("x", "damage_cap"), None), (("x", "range_factor"), None),
    (("x", "range"), "All range"), (("x", "range_unit"), None),
    (("x", "ranged_damage_type"), None), (("x", "min_hp_max"), "All HP"),
    (("x", "radius_offset"), None), (("x", "cooldown_decrease"), None),
])
def test_category_of(path, cat):
    assert category_of(path) == cat


def test_every_category_is_populated(tree):
    seen = {category_of(p) for p, leaf in tree.leaves.items() if leaf.kind == "num"}
    assert set(CATEGORY_NAMES) <= seen
