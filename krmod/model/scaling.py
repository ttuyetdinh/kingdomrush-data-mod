"""Percent scaling math, rounding rules and value warnings."""

from __future__ import annotations

import decimal
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from krmod.model.values import KeyPath

PCT_MIN = 0.0
PCT_MAX = 500.0
PCT_MID = 100.0
# The game writes "no limit" as a huge number (the sniper's max_range is 1e+99).
UNLIMITED = 1e15

_WHOLE = Decimal(1)
_TENTH = Decimal("0.1")
_HUNDRED = Decimal(100)


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
        if abs(original) >= UNLIMITED:
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
        return _common_pct_search(nonzero)


def _common_pct_search(nonzero: Sequence[tuple[float, float]]) -> float | None:
    """Fallback for rows whose levels round differently: a percent on the 0.1 grid that maps every
    pair, found inside the bracket every pair allows. Prefers a whole percent, then the middle."""
    if any(abs(o) >= 1e15 for o, _ in nonzero):
        return None
    lows: list[Decimal] = []
    highs: list[Decimal] = []
    for o, c in nonzero:
        d_o = _dec(round(float(o), 6))
        step = _WHOLE if d_o == d_o.to_integral_value() else Decimal(10) ** -max(2, original_decimals(o))
        mid = _dec(c) / _dec(o) * _HUNDRED
        half = abs(step / 2 / d_o * _HUNDRED)
        lows.append(mid - half)
        highs.append(mid + half)
    low = max(lows)
    high = min(highs)
    if low > high:
        return None
    first = (low * 10).to_integral_value(rounding=decimal.ROUND_FLOOR)
    last = (high * 10).to_integral_value(rounding=decimal.ROUND_CEILING)
    middle = (low + high) / 2
    found: list[Decimal] = []
    k = first
    while k <= last:
        pct = k / 10
        if all(scale(o, float(pct)) == c for o, c in nonzero):
            found.append(pct)
        k += 1
    if not found:
        return None
    whole = [f for f in found if f == f.to_integral_value()]
    return float(min(whole or found, key=lambda f: abs(f - middle)))


def warn(path: KeyPath, value: float) -> str | None:
    """Short human warning for allowed but suspicious values, else None."""
    if value < 0:
        return "Negative values can break the game."
    if value == 0:
        key = ".".join(str(s) for s in path if isinstance(s, str)).lower()
        if "cooldown" in key or "duration" in key:
            return "Zero cooldown or duration can break the game."
    return None
