"""Stand-in for nicegui's native WindowProxy, used to test the folder picker flow."""
from __future__ import annotations

from nicegui import app

BEHAVIOR: object = None  # a tuple of paths, None (cancelled) or an Exception to raise
CALLS: list[dict] = []


class FakeWindow:
    async def create_file_dialog(self, dialog_type=None, directory="", **kwargs):
        CALLS.append({"dialog_type": dialog_type, "directory": directory})
        if isinstance(BEHAVIOR, Exception):
            raise BEHAVIOR
        return BEHAVIOR

    def signal_server_shutdown(self) -> None:  # called by nicegui on shutdown
        pass

    def set_title(self, title: str) -> None:
        pass

    def destroy(self) -> None:
        pass


def install(behavior: object) -> None:
    global BEHAVIOR
    BEHAVIOR = behavior
    CALLS.clear()
    app.native.main_window = FakeWindow()


def uninstall() -> None:
    app.native.main_window = None
