"""Step and parse rules for the number boxes: level cells, percentage boxes, live controls
and the extra points boxes."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal

from krmod.model.scaling import PCT_MAX, PCT_MID, PCT_MIN, original_decimals

SHIFT_FACTOR = 10
PCT_STEP = Decimal(1)
_TENTH = Decimal("0.1")

ENEMY_MAX = 100
ENEMY_VALUES: tuple[float, ...] = (0.25,) + tuple(float(n) for n in range(1, ENEMY_MAX + 1))
TROOP_MIN = -10
TROOP_MAX = 100
# Extra hero skill points and skill tree points are added to the game's own totals.
EXTRA_POINTS_MAX = 999
# Gaps between groups of a wave, in percent of the game's own waits.
GAP_MIN = 10
GAP_MAX = 500
GAP_STEP = 10

_ASCII_NUMBER_RE = re.compile(r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$")


def parse_number(text: str) -> float:
    """ASCII decimal number to float. Raises ValueError with a short message otherwise."""
    if not isinstance(text, str):
        raise ValueError("Not a number.")
    s = text.strip()
    if not s:
        raise ValueError("Value cannot be empty.")
    if not _ASCII_NUMBER_RE.match(s):
        raise ValueError("Not a number.")
    val = float(s)
    if not math.isfinite(val):
        raise ValueError("Not a number.")
    return val


def cell_step(original: float, shift: bool = False) -> Decimal:
    """One step for a level cell: the smallest digit of the original (150 -> 1, 0.8 -> 0.1,
    0.15 -> 0.01), times SHIFT_FACTOR with Shift held."""
    step = Decimal(10) ** -original_decimals(original)
    return step * SHIFT_FACTOR if shift else step


def step_cell(current: float, original: float, direction: int, shift: bool = False) -> float:
    """current moved one step up (direction 1) or down (-1). A value at or above 0 stops at 0."""
    new = Decimal(str(current)) + direction * cell_step(original, shift)
    if new < 0 <= current:
        new = Decimal(0)
    return float(new)


def parse_pct(text: str) -> float:
    """'150', '150%' or ' 99.5 % ' to a percent clamped to PCT_MIN..PCT_MAX, rounded to 0.1."""
    s = text.strip() if isinstance(text, str) else text
    if isinstance(s, str) and s.endswith("%"):
        s = s[:-1]
    return clamp_pct(parse_number(s))


def clamp_pct(pct: float) -> float:
    pct = min(PCT_MAX, max(PCT_MIN, float(pct)))
    return float(Decimal(str(pct)).quantize(_TENTH, rounding=ROUND_HALF_UP))


def step_pct(current: float | None, direction: int, shift: bool = False) -> float:
    """Percent box step: 1% (10% with Shift). A mixed box (None) steps from 100%."""
    base = PCT_MID if current is None else current
    step = PCT_STEP * SHIFT_FACTOR if shift else PCT_STEP
    return clamp_pct(float(Decimal(str(base)) + direction * step))


def snap_enemy(value: float) -> float:
    """Nearest allowed enemy multiplier; a tie goes to the larger value."""
    return min(ENEMY_VALUES, key=lambda v: (abs(v - value), -v))


def step_enemy(current: float, direction: int, shift: bool = False) -> float:
    """Next allowed multiplier. Shift jumps to the next multiple of ten (1 -> 10 -> 20, and back
    20 -> 10 -> 1); below 1 and at the ends it moves like a plain step."""
    cur = snap_enemy(current)
    if shift and cur >= 1:
        tens = math.floor(cur / SHIFT_FACTOR) + 1 if direction > 0 else math.ceil(cur / SHIFT_FACTOR) - 1
        target = min(ENEMY_MAX, max(1, tens * SHIFT_FACTOR))
        if target != cur:
            return float(target)
    i = ENEMY_VALUES.index(cur) + direction
    return ENEMY_VALUES[min(len(ENEMY_VALUES) - 1, max(0, i))]


def clamp_troop(value: float) -> int:
    """Whole number of extra soldiers, half away from zero, clamped to TROOP_MIN..TROOP_MAX."""
    whole = int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(TROOP_MAX, max(TROOP_MIN, whole))


def step_troop(current: int, direction: int, shift: bool = False) -> int:
    return clamp_troop(current + direction * (SHIFT_FACTOR if shift else 1))


def clamp_points(value: float) -> int:
    """Whole number of extra points, half up, clamped to 0..EXTRA_POINTS_MAX."""
    whole = int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(EXTRA_POINTS_MAX, max(0, whole))


def step_points(current: int, direction: int, shift: bool = False) -> int:
    return clamp_points(current + direction * (SHIFT_FACTOR if shift else 1))


def clamp_gap(value: float) -> int:
    """Whole percent of the game's gaps between groups, half up, clamped to GAP_MIN..GAP_MAX."""
    whole = int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(GAP_MAX, max(GAP_MIN, whole))


def step_gap(current: int, direction: int, shift: bool = False) -> int:
    """Gaps box step: 10% (100% with Shift)."""
    return clamp_gap(current + direction * GAP_STEP * (SHIFT_FACTOR if shift else 1))
