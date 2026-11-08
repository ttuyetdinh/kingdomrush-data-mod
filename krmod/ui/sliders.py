"""Sliders (C1 and C2) for card, row, and per-level stat scaling."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from krmod.model.rows import StatRow
from krmod.model.scaling import (
    PCT_MID,
    c2_range,
    original_decimals,
    pct_to_track,
    track_to_pct,
)
from krmod.model.values import KeyPath, path_str
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


class CardSliders:
    """C1 sliders for whole-card scaling (All costs, All damage, etc.)."""

    def __init__(
        self,
        state: AppState,
        card_id: str,
        on_change: Callable[[], None],
    ) -> None:
        self.state = state
        self.card_id = card_id
        self.on_change = on_change
        self.sliders: dict[str, ui.slider] = {}
        self.labels: dict[str, ui.label] = {}

        self._build()

    def _build(self) -> None:
        categories = self.state.card_categories(self.card_id)
        if not categories:
            return

        with ui.column().classes("w-full bg-slate-50 border border-slate-200 rounded-lg p-3 gap-2 mb-3 shrink-0"):
            with ui.row().classes("items-center justify-between w-full mb-1"):
                ui.label("Quick scale all levels").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                ui.label("0% to 500% (center = 100%)").classes("text-xs text-slate-400 italic")

            for cat in categories:
                pct = self.state.card_pct(self.card_id, cat)
                track_val = pct_to_track(pct if pct is not None else PCT_MID)

                cat_slug = cat.replace(" ", "-").lower()
                with ui.row().classes("items-center w-full gap-3"):
                    ui.label(cat).classes("w-28 text-xs font-medium text-slate-700")

                    slider = (
                        ui.slider(min=0.0, max=1.0, step=0.00125, value=track_val)
                        .classes("flex-1")
                        .mark(f"card-slider-{cat_slug}")
                    )
                    slider.on("change", lambda e, c=cat, s=slider: self._on_slide(c, s, e))
                    self.sliders[cat] = slider

                    val_lbl = ui.label(format_pct(pct)).classes(
                        "w-14 text-right text-xs font-mono font-bold text-slate-700"
                    ).mark(f"card-val-{cat_slug}")
                    if pct is not None and pct != 100.0:
                        val_lbl.classes(add="text-amber-600")
                    self.labels[cat] = val_lbl

    def _on_slide(self, category: str, slider: ui.slider, e: Any) -> None:
        raw_val = e.args if (e.args is not None and isinstance(e.args, (int, float))) else slider.value
        track_val = float(raw_val if raw_val is not None else 0.5)
        new_pct = track_to_pct(track_val)
        self.state.scale_card(self.card_id, category, new_pct)
        self.on_change()

    def refresh(self) -> None:
        for cat, slider in self.sliders.items():
            pct = self.state.card_pct(self.card_id, cat)
            slider.value = pct_to_track(pct if pct is not None else PCT_MID)
            lbl = self.labels.get(cat)
            if lbl:
                lbl.text = format_pct(pct)
                if pct is not None and pct != 100.0:
                    lbl.classes(add="text-amber-600")
                else:
                    lbl.classes(remove="text-amber-600")


class RowSlider:
    """C1 slider for scaling all levels of a single StatRow."""

    def __init__(
        self,
        state: AppState,
        row: StatRow,
        on_change: Callable[[], None],
    ) -> None:
        self.state = state
        self.row = row
        self.on_change = on_change

        row_slug = row.id.replace(" ", "-").replace(".", "-")
        pct = self.state.row_pct(row)
        track_val = pct_to_track(pct if pct is not None else PCT_MID)

        with ui.row().classes("items-center justify-end gap-2 no-wrap w-full"):
            self.slider = (
                ui.slider(min=0.0, max=1.0, step=0.00125, value=track_val)
                .classes("w-24")
                .mark(f"row-slider-{row_slug}")
            )
            self.slider.on("change", self._on_slide)

            self.val_label = ui.label(format_pct(pct)).classes(
                "w-12 text-right text-xs font-mono font-medium text-slate-600"
            ).mark(f"row-val-{row_slug}")
            if pct is not None and pct != 100.0:
                self.val_label.classes(add="text-amber-600 font-bold")

    def _on_slide(self, e: Any) -> None:
        raw_val = e.args if (e.args is not None and isinstance(e.args, (int, float))) else self.slider.value
        track_val = float(raw_val if raw_val is not None else 0.5)
        new_pct = track_to_pct(track_val)
        self.state.scale_row(self.row, new_pct)
        self.on_change()

    def refresh(self) -> None:
        pct = self.state.row_pct(self.row)
        self.slider.value = pct_to_track(pct if pct is not None else PCT_MID)
        self.val_label.text = format_pct(pct)
        if pct is not None and pct != 100.0:
            self.val_label.classes(add="text-amber-600 font-bold")
        else:
            self.val_label.classes(remove="text-amber-600 font-bold")


class C2Panel:
    """C2 slider panel for per-level editing with before/after bars and lock toggle."""

    def __init__(
        self,
        state: AppState,
        row: StatRow,
        on_change: Callable[[], None],
        container: ui.element,
    ) -> None:
        self.state = state
        self.row = row
        self.on_change = on_change
        self.container = container

        self.sliders: dict[KeyPath, ui.slider] = {}
        self.val_labels: dict[KeyPath, ui.label] = {}
        self.curr_bars: dict[KeyPath, ui.element] = {}
        self.low = 0.0
        self.high = 10.0

        self._build()

    def _build(self) -> None:
        self.low, self.high = self.state.c2_range(self.row)

        max_dec = max(
            (original_decimals(self.state.original(p)) for p in self.row.cells if p is not None),
            default=0,
        )
        if max_dec >= 4:
            step = 0.0001
        elif max_dec == 3:
            step = 0.001
        elif max_dec > 0:
            step = 0.01
        else:
            step = 1.0

        row_slug = self.row.id.replace(" ", "-").replace(".", "-")

        with self.container:
            with ui.row().classes("items-center justify-between w-full pb-2 border-b border-slate-200"):
                ui.label(f"{self.row.label}, per level").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                self.lock_switch = (
                    ui.switch("Move all levels together", value=False)
                    .props("dense")
                    .mark(f"c2-lock-{row_slug}")
                )

            for i, p in enumerate(self.row.cells):
                if p is None:
                    continue
                orig = self.state.original(p)
                curr = self.state.current(p)

                p_str = path_str(p)
                with ui.column().classes("w-full gap-0.5 pt-1"):
                    with ui.row().classes("items-center w-full gap-3"):
                        ui.label(f"Level {i + 1}").classes("w-20 text-xs font-medium text-slate-600")

                        slider = (
                            ui.slider(min=self.low, max=self.high, step=step, value=curr)
                            .classes("flex-1")
                            .mark(f"c2-slider-{p_str}")
                        )
                        slider.on("change", lambda e, path=p, s=slider: self._on_slide(path, s, e))
                        self.sliders[p] = slider

                        val_lbl = ui.label(format_val(curr)).classes(
                            "w-16 text-right text-xs font-mono font-bold text-slate-800"
                        ).mark(f"c2-val-{p_str}")
                        if curr != orig:
                            val_lbl.classes(add="text-amber-600")
                        self.val_labels[p] = val_lbl

                    # Before/After comparison bars (grey = orig, blue = current):
                    orig_pct = min(100.0, max(0.0, (orig / self.high) * 100.0)) if self.high > 0 else 0.0
                    curr_pct = min(100.0, max(0.0, (curr / self.high) * 100.0)) if self.high > 0 else 0.0

                    with ui.column().classes("w-full pl-24 pr-20 gap-0.5"):
                        ui.element("div").classes(
                            "h-1.5 bg-slate-300 rounded transition-all"
                        ).style(f"width: {orig_pct}%;").mark(f"c2-bar-orig-{p_str}")

                        curr_bar = ui.element("div").classes(
                            "h-1.5 bg-blue-500 rounded transition-all"
                        ).style(f"width: {curr_pct}%;").mark(f"c2-bar-curr-{p_str}")
                        self.curr_bars[p] = curr_bar

    def _on_slide(self, path: KeyPath, slider: ui.slider, e: Any) -> None:
        raw_val = e.args if (e.args is not None and isinstance(e.args, (int, float))) else slider.value
        val = float(raw_val if raw_val is not None else 0.0)
        is_locked = bool(self.lock_switch.value)
        warning = self.state.set_level(path, val, locked_row=self.row if is_locked else None)
        if warning:
            ui.notify(warning, color="warning")
        self.on_change()

    def refresh(self) -> None:
        for p, slider in self.sliders.items():
            orig = self.state.original(p)
            curr = self.state.current(p)
            slider.value = curr

            lbl = self.val_labels.get(p)
            if lbl:
                lbl.text = format_val(curr)
                if curr != orig:
                    lbl.classes(add="text-amber-600")
                else:
                    lbl.classes(remove="text-amber-600")

            bar = self.curr_bars.get(p)
            if bar:
                curr_pct = min(100.0, max(0.0, (curr / self.high) * 100.0)) if self.high > 0 else 0.0
                bar.style(f"width: {curr_pct}%;")


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
