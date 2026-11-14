"""Slider categories: which "All ..." bulk slider a numeric value belongs to."""
from __future__ import annotations

from .values import KeyPath, is_enum_key

CATEGORY_NAMES = (
    "All costs", "All damage", "All range", "All cooldowns", "All HP", "All moving speed",
)

_COSTS = frozenset({
    "price", "prices", "cost", "repair_cost", "knight_cost", "attack_cost",
    "attack_cost_iron",
})
_HP = frozenset({"hp", "hp_max", "hp_base", "health", "min_hp_max", "max_hp_max"})
# How fast a unit walks (enemies, heroes, soldiers); factors and attack speeds stay out.
_MOVING_SPEED = frozenset({"speed", "movement_speed"})

# damage_red is a damage reduction (a debuff factor and its duration), not damage dealt.
_DAMAGE_EXCLUDE = ("type", "radius", "factor", "every", "cap", "inc", "mult", "damage_red", "duration")
# Retarget ranges are how far a shot may jump to a new enemy when its target dies, not reach;
# "ranged" names ranged attacks (basic_ranged_attack_ptg), not a distance.
_RANGE_EXCLUDE = ("factor", "inc", "unit", "offset", "retarget", "ranged")
_COOLDOWN_EXCLUDE = ("factor", "inc", "decrease")


def _any_in(words: tuple[str, ...], key: str) -> bool:
    return any(w in key for w in words)


def category_of(path: KeyPath) -> str | None:
    key = next((s for s in reversed(path) if isinstance(s, str)), None)
    if key is None:
        return None
    if is_enum_key(key):
        return None  # enum leaves are never scaled
    if key in _COSTS:
        return "All costs"
    if "damage" in key and not _any_in(_DAMAGE_EXCLUDE, key):
        return "All damage"
    if ("range" in key or "radius" in key) and not _any_in(_RANGE_EXCLUDE, key):
        # A minimum range is a blind spot (the sniper cannot shoot closer than min_range):
        # raising it would shrink what a unit reaches, so All range leaves it alone.
        if key.startswith("min_") or key.endswith("_min"):
            return None
        return "All range"
    if "cooldown" in key and not _any_in(_COOLDOWN_EXCLUDE, key):
        return "All cooldowns"
    if key in _HP:
        return "All HP"
    if key in _MOVING_SPEED:
        return "All moving speed"
    return None
