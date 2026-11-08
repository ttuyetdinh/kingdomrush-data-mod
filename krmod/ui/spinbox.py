"""Number box with up/down buttons inside it; the arrow keys step too (Shift held: bigger step)."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

Tone = str | None  # None, "changed", "mixed" or "pct-changed"


class SpinBox(ui.input, component="spinbox.js"):
    """A number box that never decides values itself.

    It is a single lightweight element (spinbox.js: a plain input, two buttons, an optional
    warning sign and an optional game value under it), because big tables hold hundreds of them.

    on_commit(text) runs for typed text on Enter or blur, only when the text changed.
    on_step(direction, shift) runs for the up/down buttons and the arrow keys; direction is 1 or -1.
    Uncommitted typed text is committed before a step. The owner validates, saves and then
    calls set_text() with the value to show (also to revert rejected text).
    on_reset() runs when the struck game value shown by set_original() is clicked.

    Events (for tests): "commit", "step" with {"direction": 1 | -1, "shiftKey": bool}, "reset".
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
        on_reset: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(value=text)
        self._shown = text
        self._on_commit = on_commit
        self._on_step = on_step
        self._props["box-class"] = classes
        self._props["dark"] = dark
        self.mark(marker)
        self.on("commit", lambda _: self.commit())
        self.on("step", self._handle_step)
        if on_reset is not None:
            self.on("reset", lambda _: on_reset())

    @property
    def text(self) -> str:
        return self._shown

    def set_text(self, text: str) -> None:
        self._shown = text
        self.value = text

    def set_tone(self, tone: Tone) -> None:
        self._set_prop("tone", tone)

    def set_original(self, text: str | None) -> None:
        """Show the struck game value under the box (None hides it)."""
        self._set_prop("original", text)

    def set_warning(self, text: str | None) -> None:
        self._set_prop("warning", text)

    def commit(self) -> None:
        typed = str(self.value if self.value is not None else "")
        if typed != self._shown:
            self._on_commit(typed)

    def _set_prop(self, name: str, value: Any) -> None:
        if self._props.get(name) != value:
            self._props[name] = value

    def _handle_step(self, e: Any) -> None:
        args = e.args if isinstance(e.args, dict) else {}
        direction = 1 if int(args.get("direction", 1)) > 0 else -1
        self.commit()
        self._on_step(direction, bool(args.get("shiftKey")))
