"""Number box with up/down buttons inside it; the arrow keys step too (Shift held: bigger step)."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

_INPUT_PROPS = 'dense outlined hide-bottom-space input-class="text-right"'
_ARROW_PROPS = "flat dense round size=xs padding=0"
_ARROW_CLASSES = "min-h-0 h-3 w-4 leading-none"


def _shift(e: Any) -> bool:
    args = getattr(e, "args", None)
    return bool(args.get("shiftKey")) if isinstance(args, dict) else False


class SpinBox:
    """A text box that never decides values itself.

    on_commit(text) runs for typed text on Enter or blur, only when the text changed.
    on_step(direction, shift) runs for the up/down buttons and the arrow keys; direction is 1 or -1.
    Uncommitted typed text is committed before a step. The owner validates, saves and then
    calls set_text() with the value to show (also to revert rejected text).

    Markers: <marker> on the input, <marker>-up and <marker>-down on the buttons.
    """

    def __init__(
        self,
        text: str,
        *,
        on_commit: Callable[[str], None],
        on_step: Callable[[int, bool], None],
        marker: str,
        classes: str = "w-24",
        dark: bool = False,
    ) -> None:
        self._shown = text
        self._on_commit = on_commit
        self._on_step = on_step

        props = _INPUT_PROPS + (" dark" if dark else "")
        self.inp = ui.input(value=text).props(props).classes(f"{classes} font-mono text-sm").mark(marker)
        with self.inp.add_slot("append"):
            with ui.column().classes("gap-0 -mr-2 items-center justify-center"):
                self.up = (
                    ui.button(icon="arrow_drop_up")
                    .props(_ARROW_PROPS)
                    .classes(_ARROW_CLASSES)
                    .mark(f"{marker}-up")
                )
                self.down = (
                    ui.button(icon="arrow_drop_down")
                    .props(_ARROW_PROPS)
                    .classes(_ARROW_CLASSES)
                    .mark(f"{marker}-down")
                )
        self.up.on("click", lambda e: self._step(1, _shift(e)), args=["shiftKey"])
        self.down.on("click", lambda e: self._step(-1, _shift(e)), args=["shiftKey"])
        self.inp.on("keydown.up.prevent", lambda e: self._step(1, _shift(e)), args=["shiftKey"])
        self.inp.on("keydown.down.prevent", lambda e: self._step(-1, _shift(e)), args=["shiftKey"])
        self.inp.on("keydown.enter", lambda _: self.commit())
        self.inp.on("blur", lambda _: self.commit())

    @property
    def text(self) -> str:
        return self._shown

    def set_text(self, text: str) -> None:
        self._shown = text
        self.inp.value = text

    def commit(self) -> None:
        typed = str(self.inp.value if self.inp.value is not None else "")
        if typed != self._shown:
            self._on_commit(typed)

    def _step(self, direction: int, shift: bool) -> None:
        self.commit()
        self._on_step(direction, shift)
