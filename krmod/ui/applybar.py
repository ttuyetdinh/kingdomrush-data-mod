"""Apply bar component: Reset all, Apply mod, Apply mod and run game, and log summary watcher."""
from __future__ import annotations

import time
from typing import Any

from nicegui import ui

from krmod.modgen.launcher import RunOutcome
from krmod.modgen.logwatch import LogSummary, LogWatcher
from krmod.state import AppState


def render(state: AppState) -> None:
    """Render the bottom action bar."""
    watcher: LogWatcher | None = None
    poll_timer: ui.timer | None = None
    last_outcome: RunOutcome | None = None
    poll_start_time: float = 0.0

    # Confirmation dialog for Reset all
    with ui.dialog() as reset_dialog, ui.card().classes(
        "p-4 min-w-[320px] gap-4"
    ):
        ui.label("Reset all changes?").classes("text-base font-bold text-slate-900")
        ui.label(
            "This will revert all stat changes in the active profile back to vanilla."
        ).classes("text-xs text-slate-500")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=reset_dialog.close).props("flat dense")

            def do_reset() -> None:
                state.reset_all()
                reset_dialog.close()
                from krmod.ui import main as ui_main

                ui_main.refresh()
                ui.notify("All changes reset", color="info")

            ui.button("Reset", on_click=do_reset).props(
                "unelevated dense color=negative"
            ).mark("btn-confirm-reset")

    # Dismissible dialog for Log summary
    with ui.dialog() as summary_dialog, ui.card().classes(
        "p-5 min-w-[420px] max-w-lg gap-3"
    ).mark("log-summary-panel"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Mod Loader Log").classes("font-bold text-slate-900 text-base")
            ui.button(icon="close", on_click=summary_dialog.close).props(
                "flat round dense"
            )
        summary_content = ui.column().classes("w-full gap-2")

    def show_log_summary(summary: LogSummary) -> None:
        summary_content.clear()
        with summary_content:
            if last_outcome == RunOutcome.UPDATED_RUNNING:
                ui.label(
                    "Game is running: changes apply at the next level start"
                ).classes(
                    "text-xs text-blue-700 bg-blue-50 p-2 rounded border border-blue-200"
                )
            else:
                if summary.applied is not None:
                    ui.label(f"Applied: {summary.applied} changes").classes(
                        "text-sm font-semibold text-slate-800"
                    )
                else:
                    ui.label("Mod loaded").classes(
                        "text-sm font-semibold text-slate-800"
                    )

            if summary.errors:
                with ui.column().classes(
                    "w-full p-2 bg-red-50 border border-red-200 rounded gap-1"
                ):
                    ui.label("Errors:").classes("text-xs font-bold text-red-700")
                    for err in summary.errors:
                        ui.label(f"• {err}").classes("text-xs text-red-600 font-mono")

            if summary.missing:
                with ui.column().classes(
                    "w-full p-2 bg-amber-50 border border-amber-200 rounded gap-1"
                ):
                    ui.label("Missing paths:").classes(
                        "text-xs font-bold text-amber-800"
                    )
                    for miss in summary.missing:
                        ui.label(f"• {miss}").classes(
                            "text-xs text-amber-700 font-mono"
                        )

            if summary.unlock:
                with ui.column().classes(
                    "w-full p-2 bg-slate-50 border border-slate-200 rounded gap-1"
                ):
                    ui.label("Rules:").classes("text-xs font-bold text-slate-700")
                    for unl in summary.unlock:
                        ui.label(f"• {unl}").classes("text-xs text-slate-600")

        summary_dialog.open()

    def check_log() -> None:
        nonlocal poll_timer
        if watcher is None:
            if poll_timer:
                poll_timer.deactivate()
            return

        if time.time() - poll_start_time > 120:
            if poll_timer:
                poll_timer.deactivate()
            return

        summary = watcher.poll()
        if summary is not None:
            if poll_timer:
                poll_timer.deactivate()
            show_log_summary(summary)

    def start_polling() -> None:
        nonlocal poll_timer, poll_start_time
        poll_start_time = time.time()
        if poll_timer is not None:
            poll_timer.activate()
        else:
            poll_timer = ui.timer(1.0, check_log)

    def on_apply_mod() -> None:
        nonlocal watcher, last_outcome
        last_outcome = None
        log_file = state.paths.mods_dir / "kr_mod_log.txt"
        watcher = LogWatcher(log_file)
        watcher.mark()
        res = state.apply()
        ui.notify(f"Mod written: {res.applied} changes", color="positive")
        from krmod.ui import main as ui_main

        ui_main.refresh()
        start_polling()

    def on_apply_and_run() -> None:
        nonlocal watcher, last_outcome
        log_file = state.paths.mods_dir / "kr_mod_log.txt"
        watcher = LogWatcher(log_file)
        watcher.mark()
        outcome, res = state.apply_and_run()
        last_outcome = outcome
        from krmod.ui import main as ui_main

        ui_main.refresh()

        if outcome == RunOutcome.UPDATED_RUNNING:
            msg = "Game is running: changes apply at the next level start"
            status_label.text = msg
            status_label.visible = True
            ui.notify(msg, color="info")
        elif outcome == RunOutcome.NEEDS_RESTART:
            msg = (
                "The game was started without the mod. Close it and use Apply mod and run game."
            )
            status_label.text = msg
            status_label.visible = True
            ui.notify(msg, color="warning")
        elif outcome == RunOutcome.LAUNCHED:
            msg = "Waiting for the game to load the mod"
            status_label.text = msg
            status_label.visible = True
            ui.notify(msg, color="positive")

        start_polling()

    # Left controls: Reset all and status message
    with ui.row().classes("items-center gap-4"):
        ui.button("Reset all", on_click=reset_dialog.open).props(
            "flat dense color=negative"
        ).mark("reset-all")
        status_label = ui.label("").classes("text-xs text-slate-500 italic")
        status_label.visible = False

    # Right controls: Apply mod and Apply mod and run game
    with ui.row().classes("items-center gap-3"):
        ui.button("Apply mod", on_click=on_apply_mod).props(
            "outline dense color=primary"
        ).mark("apply-mod")
        ui.button("Apply mod and run game", on_click=on_apply_and_run).props(
            "unelevated dense color=primary"
        ).mark("apply-run")
