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
    (("enemies", "orcs", "goblin", "speed"), "All moving speed"),
    (("x", "movement_speed"), "All moving speed"), (("x", "speed_mult", 1), None),
    (("x", "slide_speed_factor"), None),
    # lower bounds and retarget jumps are not reach: raising them would not widen it
    (("towers", "sniper", "basic_attack", "min_range", 1), None),
    (("x", "min_detection_range"), None), (("x", "range_nodes_min"), None),
    (("x", "min_radius"), None), (("x", "max_range", 1), "All range"),
    (("towers", "sniper", "basic_attack", "max_retarget_range"), None),
    (("towers", "sniper", "ultimate", "retarget_range"), None),
    (("x", "clone", "basic_ranged_attack_ptg"), None),
    (("x", "s_damage_red"), None), (("x", "damage_red_duration"), None),
    (("x", "min_damage"), "All damage"),
])
def test_category_of(path, cat):
    assert category_of(path) == cat


def test_every_category_is_populated(tree):
    seen = {category_of(p) for p, leaf in tree.leaves.items() if leaf.kind == "num"}
    assert set(CATEGORY_NAMES) <= seen


def test_enum_rule_is_shared(tree):
    from krmod.model.values import Leaf, is_enum_key

    assert is_enum_key("damage_type") and is_enum_key("ranged_damage_type")
    assert not is_enum_key("damage_types") and not is_enum_key(1) and not is_enum_key(None)
    for p, leaf in tree.leaves.items():
        if leaf.kind == "num":
            assert leaf.is_enum == is_enum_key(p[-1])
            if leaf.is_enum:
                assert category_of(p) is None
    assert Leaf(("x", "damage_type"), 3, "num").is_enum
    assert not Leaf(("x", "damage_type"), "a", "str").is_enum
