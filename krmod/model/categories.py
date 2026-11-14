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

_DAMAGE_EXCLUDE = ("type", "radius", "factor", "every", "cap", "inc", "mult")
_RANGE_EXCLUDE = ("factor", "inc", "unit", "offset")
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
        return "All range"
    if "cooldown" in key and not _any_in(_COOLDOWN_EXCLUDE, key):
        return "All cooldowns"
    if key in _HP:
        return "All HP"
    if key in _MOVING_SPEED:
        return "All moving speed"
    return None
