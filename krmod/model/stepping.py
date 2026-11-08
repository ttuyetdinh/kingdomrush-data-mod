"""Step and parse rules for the number boxes: level cells, percentage boxes and live controls."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal

from krmod.model.scaling import PCT_MAX, PCT_MID, PCT_MIN, original_decimals

SHIFT_FACTOR = 10
PCT_STEP = Decimal(1)
_TENTH = Decimal("0.1")

ENEMY_VALUES: tuple[float, ...] = (0.25,) + tuple(float(n) for n in range(1, 11))
TROOP_MIN = -10
TROOP_MAX = 10

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


def step_enemy(current: float, direction: int) -> float:
    i = ENEMY_VALUES.index(snap_enemy(current))
    return ENEMY_VALUES[min(len(ENEMY_VALUES) - 1, max(0, i + direction))]


def clamp_troop(value: float) -> int:
    """Whole number of extra soldiers, half away from zero, clamped to TROOP_MIN..TROOP_MAX."""
    whole = int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return min(TROOP_MAX, max(TROOP_MIN, whole))


def step_troop(current: int, direction: int) -> int:
    return clamp_troop(current + direction)
