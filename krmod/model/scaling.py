"""Slider math, rounding rules and value warnings."""

from __future__ import annotations

import decimal
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from krmod.model.values import KeyPath

PCT_MIN = 0.0
PCT_MAX = 500.0
PCT_MID = 100.0

_WHOLE = Decimal(1)
_TENTH = Decimal("0.1")
_HUNDRED = Decimal(100)


def track_to_pct(t: float) -> float:
    """Slider track position 0..1 to percent: left half 0..100, right half 100..500."""
    t = min(1.0, max(0.0, t))
    if t <= 0.5:
        return PCT_MIN + (PCT_MID - PCT_MIN) * (t / 0.5)
    return PCT_MID + (PCT_MAX - PCT_MID) * ((t - 0.5) / 0.5)


def pct_to_track(p: float) -> float:
    """Exact inverse of track_to_pct."""
    p = min(PCT_MAX, max(PCT_MIN, p))
    if p <= PCT_MID:
        return (p - PCT_MIN) / (PCT_MID - PCT_MIN) * 0.5
    return 0.5 + (p - PCT_MID) / (PCT_MAX - PCT_MID) * 0.5


def _dec(x: float | int) -> Decimal:
    return Decimal(str(x))


def original_decimals(x: float | int) -> int:
    """Number of decimal places after normalizing to at most 6 decimals. Whole numbers return 0."""
    d = Decimal(str(round(float(x), 6))).normalize()
    if d == d.to_integral_value():
        return 0
    return -d.as_tuple().exponent


def scale(original: float, pct: float) -> float:
    """original x pct%, half-up (away from zero). Whole originals give whole results,
    decimal originals keep max(2, original decimals) places."""
    if float(pct) == 100.0:
        return original
    with decimal.localcontext(decimal.Context(prec=400)):
        if abs(original) >= 1e15:
            return float(Decimal(str(original)) * Decimal(str(pct)) / _HUNDRED)
        d_orig = Decimal(str(round(float(original), 6))).normalize()
        if d_orig == d_orig.to_integral_value():
            step = _WHOLE
        else:
            places = max(2, original_decimals(original))
            step = Decimal(10) ** -places
        exact = d_orig * _dec(pct) / _HUNDRED
        return float(exact.quantize(step, rounding=ROUND_HALF_UP))


def common_pct(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Percent that maps every nonzero original to its current value, or None if mixed."""
    nonzero = [(o, c) for o, c in pairs if o != 0]
    if not nonzero:
        return 100.0
    o_ref, c_ref = max(nonzero, key=lambda oc: abs(oc[0]))
    with decimal.localcontext(decimal.Context(prec=400)):
        candidate = (_dec(c_ref) / _dec(o_ref) * _HUNDRED).quantize(_TENTH, rounding=ROUND_HALF_UP)
        pct = float(candidate)
        if all(scale(o, pct) == c for o, c in nonzero):
            return pct
        return None


def c2_range(originals: Sequence[float]) -> tuple[float, float]:
    """Row editing range: 0 to max(10, 3 x largest absolute original)."""
    biggest = max((abs(o) for o in originals), default=0)
    return (0.0, float(max(10, 3 * biggest)))


def warn(path: KeyPath, value: float) -> str | None:
    """Short human warning for allowed but suspicious values, else None."""
    if value < 0:
        return "Negative values can break the game."
    if value == 0:
        key = ".".join(str(s) for s in path if isinstance(s, str)).lower()
        if "cooldown" in key or "duration" in key:
            return "Zero cooldown or duration can break the game."
    return None
