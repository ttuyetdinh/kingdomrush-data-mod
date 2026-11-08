"""Shared value and percent formatting, plus the live enemy/troop slider."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from krmod.model.scaling import original_decimals
from krmod.profiles import ProfileError
from krmod.state import AppState


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


def live_slider(
    state: AppState,
    field: str,
    prefix: str,
    marker: str,
    on_refresh: Callable[[], None],
    *,
    slider_classes: str = "w-full",
    label_classes: str = "text-xs font-mono whitespace-nowrap",
    wrapper_classes: str = "w-[90px] shrink-0",
    slider_props: str = "",
) -> tuple[ui.label, ui.slider]:
    """Shared helper for live enemy/troop multiplier sliders."""
    val = float(getattr(state.profile.live, field))
    label = ui.label(f"{prefix} {val:g}x").classes(label_classes)
    with ui.element("div").classes(wrapper_classes):
        slider = (
            ui.slider(min=0.5, max=3.0, step=0.25, value=val)
            .classes(slider_classes)
            .mark(marker)
        )
        if slider_props:
            slider.props(slider_props)
    def on_change(e: Any) -> None:
        raw = (
            e.args
            if (e.args is not None and isinstance(e.args, (int, float)))
            else slider.value
        )
        new_val = float(raw if raw is not None else 1.0)
        curr = float(getattr(state.profile.live, field))
        try:
            kwargs = {field: new_val}
            state.set_live(**kwargs)
            label.text = f"{prefix} {new_val:g}x"
            on_refresh()
        except ProfileError as exc:
            ui.notify(str(exc), color="negative")
            slider.value = curr
            label.text = f"{prefix} {curr:g}x"

    slider.on("change", on_change)
    return label, slider
