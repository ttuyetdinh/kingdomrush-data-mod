"""Percent box (Row % and quick scale): a SpinBox showing a percent, or 'mixed'."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.model.scaling import PCT_MID
from krmod.model.stepping import parse_pct, step_pct
from krmod.ui.sliders import format_pct
from krmod.ui.spinbox import SpinBox

_CHANGED = "text-amber-700 font-bold"
_MIXED = "text-slate-400 italic"


class PctBox:
    """Percent box built on SpinBox.

    get_pct() returns the current percent, or None when the cells disagree ("mixed").
    set_pct(pct) applies a percent (0..500). Typed text goes through parse_pct, steps through
    step_pct (1%, Shift 10%, a mixed box steps from 100%). on_change() runs after every applied value.
    """

    def __init__(
        self,
        get_pct: Callable[[], float | None],
        set_pct: Callable[[float], None],
        marker: str,
        on_change: Callable[[], None],
        *,
        classes: str = "w-24",
        dark: bool = False,
    ) -> None:
        self._get_pct = get_pct
        self._set_pct = set_pct
        self._on_change = on_change
        self.box = SpinBox(
            format_pct(get_pct()),
            on_commit=self._commit,
            on_step=self._step,
            marker=marker,
            classes=classes,
            dark=dark,
        )
        self._style(get_pct())

    def _commit(self, text: str) -> None:
        try:
            pct = parse_pct(text)
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            self.refresh()
            return
        self._apply(pct)

    def _step(self, direction: int, shift: bool) -> None:
        self._apply(step_pct(self._get_pct(), direction, shift))

    def _apply(self, pct: float) -> None:
        self._set_pct(pct)
        self.refresh()
        self._on_change()

    def refresh(self) -> None:
        pct = self._get_pct()
        self.box.set_text(format_pct(pct))
        self._style(pct)

    def _style(self, pct: float | None) -> None:
        inp = self.box.inp
        inp.classes(remove=f"{_CHANGED} {_MIXED}")
        if pct is None:
            inp.classes(add=_MIXED)
        elif pct != PCT_MID:
            inp.classes(add=_CHANGED)
