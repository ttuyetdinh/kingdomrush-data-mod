"""Live number boxes for the Enemies multiplier and the Troops soldier count."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.model.stepping import (
    clamp_troop,
    parse_number,
    snap_enemy,
    step_enemy,
    step_troop,
)
from krmod.profiles import ProfileError
from krmod.state import AppState
from krmod.ui.spinbox import SpinBox

_LABELS = {"enemy_mult": "Enemies x", "troop_delta": "Troops"}


def format_live(field: str, value: float) -> str:
    """Box text: "0.25", "1", "10" for Enemies; "0", "+2", "-1" for Troops."""
    if field == "enemy_mult":
        return f"{value:g}"
    return f"{int(value):+d}" if value else "0"


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
        if field not in _LABELS:
            raise ValueError(f"unknown live field {field!r}")
        self.state = state
        self.field = field
        self.on_refresh = on_refresh
        label_classes = "text-xs font-mono whitespace-nowrap " + (
            "text-slate-300" if dark else "font-semibold text-slate-700"
        )
        with ui.row().classes("items-center gap-1 flex-nowrap"):
            self.label = ui.label(_LABELS[field]).classes(label_classes)
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
        try:
            typed = parse_number(text)
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            self.refresh()
            return
        self._save(snap_enemy(typed) if self.field == "enemy_mult" else clamp_troop(typed))

    def _on_step(self, direction: int, shift: bool) -> None:
        current = self._current()
        if self.field == "enemy_mult":
            self._save(step_enemy(current, direction))
        else:
            self._save(step_troop(current, direction))

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
