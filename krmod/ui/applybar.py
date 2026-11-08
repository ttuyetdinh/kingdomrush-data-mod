"""Apply bar component: Reset all, Apply mod, Apply mod and run game, and log summary watcher."""
from __future__ import annotations

import asyncio
import copy
import time
from typing import Callable

from nicegui import run, ui

from krmod.modgen import launcher
from krmod.modgen.launcher import RunOutcome
from krmod.modgen.logwatch import LogSummary, LogWatcher
from krmod.state import AppState
POLL_INTERVAL_S: float = 1.0
POLL_TIMEOUT_S: float = 120.0

# One game and one mods folder: only one Apply runs at a time, across all pages.
_apply_lock = asyncio.Lock()


def render(state: AppState, on_refresh: Callable[[], None], on_reset: Callable[[], None]) -> None:
    """Render the bottom action bar. on_refresh updates the page after a write; on_reset after Reset all."""
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
                on_reset()
                ui.notify("All changes reset", color="info")

            ui.button("Reset", on_click=do_reset).props(
                "unelevated dense color=negative"
            ).mark("btn-confirm-reset")

    # Dismissible non-blocking panel for Log summary
    summary_panel = ui.card().classes(
        "fixed bottom-14 right-6 z-50 p-4 min-w-[360px] max-w-md shadow-2xl border border-slate-300 bg-white gap-2"
    ).mark("log-summary-panel")
    summary_panel.visible = False
    with summary_panel:
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Mod Loader Log").classes("font-bold text-slate-900 text-sm")
            ui.button(
                icon="close", on_click=lambda: summary_panel.set_visibility(False)
            ).props("flat round dense text-color=slate-500")
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

        status_label.visible = False
        summary_panel.visible = True

    def check_log() -> None:
        nonlocal poll_timer
        if watcher is None:
            if poll_timer:
                poll_timer.deactivate()
            return

        if time.time() - poll_start_time > POLL_TIMEOUT_S:
            status_label.visible = False
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
            poll_timer = ui.timer(POLL_INTERVAL_S, check_log)

    def set_apply_busy(busy: bool) -> None:
        for button in (apply_button, run_button):
            button.set_enabled(not busy)

    async def guarded(work: Callable[[], object]) -> object:
        """Run work off the event loop, one Apply at a time; None if the app is shutting down."""
        async with _apply_lock:
            set_apply_busy(True)
            try:
                return await run.io_bound(work)
            finally:
                set_apply_busy(False)

    async def on_apply_mod() -> None:
        nonlocal watcher, last_outcome
        if _apply_lock.locked():  # a second click while an Apply runs
            return
        summary_panel.visible = False
        status_label.text = ""
        status_label.visible = False

        log_file = state.paths.mods_dir / "kr_mod_log.txt"
        watcher = LogWatcher(log_file)
        watcher.mark()
        # Snapshot on the event loop so edits made during the write can't change it mid-write.
        profile = copy.deepcopy(state.profile)

        def scan_and_write():
            return launcher.find_game(state.paths), state.apply(profile)

        # The process scan and the file writes take a moment: keep them off the event loop.
        done = await guarded(scan_and_write)
        if done is None:  # the app is shutting down
            return
        running, res = done
        is_running_modded = running is not None and running.modded
        last_outcome = RunOutcome.UPDATED_RUNNING if is_running_modded else None

        if is_running_modded:
            msg = "Mod written: changes apply at the next level start"
            status_label.text = msg
            status_label.visible = True
            ui.notify(msg, color="info")
        else:
            ui.notify(f"Mod written: {res.applied} changes", color="positive")
        on_refresh()
        start_polling()

    async def on_apply_and_run() -> None:
        nonlocal watcher, last_outcome
        if _apply_lock.locked():  # a second click while an Apply runs
            return
        summary_panel.visible = False
        status_label.text = ""
        status_label.visible = False
        log_file = state.paths.mods_dir / "kr_mod_log.txt"
        watcher = LogWatcher(log_file)
        watcher.mark()
        profile = copy.deepcopy(state.profile)
        # Process scan, file writes and launch: keep them off the event loop.
        done = await guarded(lambda: state.apply_and_run(profile))
        if done is None:  # the app is shutting down
            return
        outcome, res = done
        last_outcome = outcome
        on_refresh()

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
        status_label = ui.label("").classes(
            "text-xs text-slate-500 italic"
        ).mark("status-line")
        status_label.visible = False

    # Right controls: Apply mod and Apply mod and run game
    with ui.row().classes("items-center gap-3"):
        apply_button = ui.button("Apply mod", on_click=on_apply_mod).props(
            "outline dense color=primary"
        ).mark("apply-mod")
        run_button = ui.button("Apply mod and run game", on_click=on_apply_and_run).props(
            "unelevated dense color=primary"
        ).mark("apply-run")
