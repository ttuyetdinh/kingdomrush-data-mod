"""Live number boxes for the Enemies multiplier, the Troops soldier count and the Gaps
between groups of a wave."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from nicegui import ui

from krmod.model.stepping import (
    clamp_gap,
    clamp_troop,
    parse_number,
    snap_enemy,
    step_enemy,
    step_gap,
    step_troop,
)
from krmod.profiles import ProfileError
from krmod.state import AppState
from krmod.ui.spinbox import SpinBox


@dataclass(frozen=True)
class _Field:
    label: str
    show: Callable[[float], str]  # box text for a value
    snap: Callable[[float], float]  # typed number -> allowed value
    step: Callable[[float, int, bool], float]  # (current, direction, shift) -> next value
    percent: bool = False  # typed text may end in "%"


_FIELDS = {
    "enemy_mult": _Field("Enemies x", lambda v: f"{v:g}", snap_enemy, step_enemy),
    "troop_delta": _Field(
        "Troops", lambda v: f"{int(v):+d}" if v else "0", clamp_troop, step_troop
    ),
    "group_gap": _Field("Gaps", lambda v: f"{int(v)}%", clamp_gap, step_gap, percent=True),
}


def format_live(field: str, value: float) -> str:
    """Box text: "0.25", "1", "100" for Enemies; "0", "+2", "-1" for Troops; "100%" for Gaps."""
    return _FIELDS[field].show(value)


class LiveBox:
    """A label and a SpinBox bound to one live setting of the active profile.

    The state is the source of truth: every accepted value goes through state.set_live (which
    validates and saves), then on_refresh runs. Rejected text is reported and reverted.
    """

    def __init__(
        self,
        state: AppState,
        field: str,
        marker: str,
        on_refresh: Callable[[], None],
        *,
        dark: bool = False,
    ) -> None:
        if field not in _FIELDS:
            raise ValueError(f"unknown live field {field!r}")
        self.state = state
        self.field = field
        self._spec = _FIELDS[field]
        self.on_refresh = on_refresh
        label_classes = "text-xs font-mono whitespace-nowrap " + (
            "text-slate-300" if dark else "font-semibold text-slate-700"
        )
        with ui.row().classes("items-center gap-1 flex-nowrap"):
            self.label = ui.label(self._spec.label).classes(label_classes)
            self.box = SpinBox(
                self._shown(),
                on_commit=self._on_commit,
                on_step=self._on_step,
                marker=marker,
                classes="w-20",
                dark=dark,
            )

    def _current(self) -> float:
        return getattr(self.state.profile.live, self.field)

    def _shown(self) -> str:
        return format_live(self.field, self._current())

    def refresh(self) -> None:
        """Re-read the value from the state (profile switch, other control, undo)."""
        self.box.set_text(self._shown())

    def _on_commit(self, text: str) -> None:
        if self._spec.percent and isinstance(text, str) and text.strip().endswith("%"):
            text = text.strip()[:-1]
        try:
            typed = parse_number(text)
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            self.refresh()
            return
        self._save(self._spec.snap(typed))

    def _on_step(self, direction: int, shift: bool) -> None:
        self._save(self._spec.step(self._current(), direction, shift))

    def _save(self, value: float) -> None:
        if value == self._current():
            self.refresh()
            return
        try:
            self.state.set_live(**{self.field: value})
        except ProfileError as exc:
            ui.notify(str(exc), color="negative")
            self.refresh()
            return
        self.refresh()
        self.on_refresh()
