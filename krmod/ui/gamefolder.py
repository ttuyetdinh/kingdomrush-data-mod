"""Game folder chooser: a native folder picker with a typed-path fallback."""
from __future__ import annotations

import os
from typing import Callable

from nicegui import app, ui


async def pick_folder(start: str) -> str | None:
    """Ask the native window for a folder; None when cancelled or no native window is available."""
    window = app.native.main_window
    if window is None:
        return None
    import webview

    dialog_type = webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG
    try:
        chosen = await window.create_file_dialog(dialog_type, directory=start)
    except Exception as exc:
        ui.notify(f"Folder picker unavailable: {exc}", color="warning")
        return None
    return chosen[0] if chosen else None


def env_override_note() -> str | None:
    if os.environ.get("KRMOD_GAME_DIR"):
        return "KRMOD_GAME_DIR is set and overrides the saved folder at startup."
    return None


def render_chooser(initial: str, on_use: Callable[[str], object]) -> None:
    """Choose button plus path input. The input is shown at once without a native window
    and after a cancelled or failed pick with one."""
    with ui.column().classes("w-full gap-2"):
        input_row = ui.row().classes("w-full items-center gap-2 flex-nowrap")
        input_row.visible = app.native.main_window is None
        with input_row:
            path_input = (
                ui.input("Game folder", value=initial)
                .props("outlined dense")
                .classes("flex-1")
                .mark("game-dir-input")
                .on("keydown.enter", lambda: on_use(path_input.value or ""))
            )
            ui.button("Use this folder", on_click=lambda: on_use(path_input.value or "")).props(
                "unelevated dense color=primary no-caps"
            ).mark("btn-use-game-folder")

        async def choose() -> None:
            chosen = await pick_folder(path_input.value or initial)
            if chosen:
                path_input.value = chosen
                on_use(chosen)
            else:
                input_row.visible = True

        ui.button("Choose game folder", icon="folder_open", on_click=choose).props(
            "unelevated no-caps color=primary"
        ).mark("btn-choose-game-folder")
