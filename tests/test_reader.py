import time
from collections import Counter

from krmod.gamedata.reader import read_balance
from krmod.model.values import decode_damage_type


def test_counts(tree):
    kinds = Counter(leaf.kind for leaf in tree.leaves.values())
    assert kinds == {"num": 5857, "str": 34, "bool": 7}
    assert tree.table_count == 1665 and tree.aliases == {}


def test_known_values(tree):
    assert tree.original(("towers", "archers", "price", 1)) == 70
    leaf = tree.leaves[("enemies", "demons", "demon_lord", "basic_attack", "damage_type")]
    assert leaf.is_enum and decode_damage_type(int(leaf.value), tree.damage_flags) == "Physical"
    hit = tree.leaves[("towers", "catapult", "ultimate", "hit_damage_type")]
    assert decode_damage_type(int(hit.value), tree.damage_flags) == "Explosion"
    assert tree.damage_flags["DAMAGE_PHYSICAL"] == 2


def test_decode_combined_flags():
    flags = {"DAMAGE_PHYSICAL": 2, "DAMAGE_NO_DODGE": 33554432, "DAMAGE_ALL": 4294967295}
    assert decode_damage_type(2 | 33554432, flags) == "Physical + No dodge"


def test_read_is_fast(game_paths):
    t = time.perf_counter()
    read_balance(game_paths)
    assert time.perf_counter() - t < 5
