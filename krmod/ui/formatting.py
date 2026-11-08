"""Shared value and percent formatting for the editor boxes."""
from __future__ import annotations

from krmod.model.scaling import original_decimals


def format_pct(pct: float | None) -> str:
    """Format percent value: 'mixed' if None, otherwise e.g. '50%', '100%', '150.5%'."""
    if pct is None:
        return "mixed"
    p = round(pct, 1)
    if p == round(p):
        return f"{int(round(p))}%"
    return f"{p:.1f}%"


def format_val(val: float | int | str | bool) -> str:
    """Format value for cell display without losing precision."""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        vf = float(val)
        if vf.is_integer():
            return str(int(vf))
        places = max(2, original_decimals(vf))
        return f"{round(vf, 6):.{places}f}"
    return str(val)
