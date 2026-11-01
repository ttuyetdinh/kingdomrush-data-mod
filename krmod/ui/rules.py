"""Rules tab view: unlock switch, speed key bindings, mirrored multipliers, and stale changes."""
from __future__ import annotations

from typing import Any

from nicegui import ui

from krmod.model.values import path_str
from krmod.profiles import FORBIDDEN_KEYS, ProfileError, validate_speed_keys
from krmod.state import AppState


def render(state: AppState) -> None:
    """Render Rules tab content in the right editor region."""
    with ui.column().classes("w-full max-w-3xl p-6 gap-6"):
        # Header
        with ui.column().classes("gap-1"):
            ui.label("Rules & Global Settings").classes(
                "text-2xl font-bold text-slate-900"
            ).mark("rules-title")
            ui.label(
                "Game-wide rules, hotkeys, and live balance multipliers"
            ).classes("text-sm text-slate-500")

        # Section 1: Progression Rules
            ui.switch(
                "Unlock all tower levels",
                value=state.profile.unlock_tower_levels,
                on_change=lambda e: state.set_unlock(bool(e.value)),
            ).mark("unlock-switch")
            ui.label(
                "Removes level restrictions from towers on all stages while keeping tower type unlocks vanilla."
            ).classes("text-xs text-slate-400 mt-1")

        # Section 2: Game Speed Hotkeys
        with ui.card().classes(
            "w-full p-4 border border-slate-200 shadow-sm rounded-lg gap-3"
        ):
            ui.label("Game Speed Keybindings").classes(
                "text-base font-semibold text-slate-800"
            )
            ui.label(
                "Configure hotkeys for ×1, ×2, and ×3 game speed. Must be distinct LÖVE key names (e.g. f5, f6, f7). Reserved keys cannot be used."
            ).classes("text-xs text-slate-500")

            err_label = ui.label("").classes(
                "text-xs text-red-600 font-medium"
            ).mark("speed-keys-error")
            err_label.visible = False

            def make_validator(idx: int, input_el: ui.input):
                def on_validate(_e: Any = None) -> None:
                    raw = (input_el.value or "").strip().lower()
                    if raw in FORBIDDEN_KEYS:
                        err_label.text = f"Key '{raw}' can't be used: reserved key"
                        err_label.visible = True
                        input_el.value = state.profile.speed_keys[idx]
                        return

                    new_keys = list(state.profile.speed_keys)
                    new_keys[idx] = raw
                    try:
                        valid = validate_speed_keys(new_keys)
                        state.set_speed_keys(valid)
                        err_label.text = ""
                        err_label.visible = False
                        input_el.value = valid[idx]
                    except ProfileError as exc:
                        msg = str(exc)
                        if raw in FORBIDDEN_KEYS or "reserved" in msg:
                            msg = f"Key '{raw}' can't be used: reserved key"
                        err_label.text = msg
                        err_label.visible = True
                        input_el.value = state.profile.speed_keys[idx]

                return on_validate

            with ui.row().classes("w-full gap-4 items-center"):
                for i, speed_num in enumerate((1, 2, 3)):
                    with ui.column().classes("gap-1 flex-1"):
                        ui.label(f"Speed ×{speed_num}").classes(
                            "text-xs font-semibold text-slate-700"
                        )
                        inp = (
                            ui.input(value=state.profile.speed_keys[i])
                            .props("outlined dense")
                            .classes("w-full font-mono text-sm")
                            .mark(f"speed-key-{speed_num}")
                        )
                        validator = make_validator(i, inp)
                        inp.on("blur", validator)
                        inp.on("keydown.enter", validator)

        # Section 3: Mirrored Multipliers
        with ui.card().classes(
            "w-full p-4 border border-slate-200 shadow-sm rounded-lg gap-4"
        ):
            ui.label("Live Multipliers").classes(
                "text-base font-semibold text-slate-800"
            )
            ui.label(
                "Mirrored controls for enemy spawn counts and troop counts (0.5× to 3× in 0.25 steps)."
            ).classes("text-xs text-slate-500")

            # Enemy multiplier
            with ui.row().classes("w-full items-center gap-4"):
                e_val = state.profile.live.enemy_mult
                e_label = ui.label(f"Enemies {e_val:g}x").classes(
                    "w-28 text-xs font-semibold text-slate-700"
                )
                e_slider = (
                    ui.slider(min=0.5, max=3.0, step=0.25, value=e_val)
                    .classes("flex-1")
                    .mark("rules-enemy-mult")
                )

                def on_e_change(e: Any) -> None:
                    raw = (
                        e.args
                        if (e.args is not None and isinstance(e.args, (int, float)))
                        else e_slider.value
                    )
                    val = float(raw if raw is not None else 1.0)
                    try:
                        state.set_live(enemy_mult=val)
                        e_label.text = f"Enemies {val:g}x"
                        from krmod.ui import main as ui_main

                        ui_main.refresh()
                    except ProfileError as exc:
                        ui.notify(str(exc), color="negative")
                        e_slider.value = state.profile.live.enemy_mult

                e_slider.on("change", on_e_change)

            # Troop multiplier
            with ui.row().classes("w-full items-center gap-4"):
                t_val = state.profile.live.troop_mult
                t_label = ui.label(f"Troops {t_val:g}x").classes(
                    "w-28 text-xs font-semibold text-slate-700"
                )
                t_slider = (
                    ui.slider(min=0.5, max=3.0, step=0.25, value=t_val)
                    .classes("flex-1")
                    .mark("rules-troop-mult")
                )

                def on_t_change(e: Any) -> None:
                    raw = (
                        e.args
                        if (e.args is not None and isinstance(e.args, (int, float)))
                        else t_slider.value
                    )
                    val = float(raw if raw is not None else 1.0)
                    try:
                        state.set_live(troop_mult=val)
                        t_label.text = f"Troops {val:g}x"
                        from krmod.ui import main as ui_main

                        ui_main.refresh()
                    except ProfileError as exc:
                        ui.notify(str(exc), color="negative")
                        t_slider.value = state.profile.live.troop_mult

                t_slider.on("change", on_t_change)

        # Section 4: Stale Changes (only rendered when non-empty)
        stale_paths = state.stale()
        if stale_paths:
            with ui.card().classes(
                "w-full p-4 border border-amber-300 bg-amber-50 shadow-sm rounded-lg gap-2"
            ).mark("stale-list"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", color="warning").classes("text-lg")
                    ui.label("Stale changes").classes(
                        "text-base font-semibold text-amber-900"
                    )
                ui.label(
                    "These changes exist in your active profile but no longer exist in the game balance data:"
                ).classes("text-xs text-amber-800")
                with ui.column().classes("w-full gap-1 mt-2"):
                    for p in stale_paths:
                        saved_val = state.profile.changes.get(p)
                        with ui.row().classes(
                            "w-full items-center justify-between py-1 px-2 bg-amber-100/60 rounded text-xs font-mono"
                        ):
                            ui.label(path_str(p)).classes("text-amber-950")
                            ui.label(str(saved_val)).classes(
                                "font-bold text-amber-900"
                            )
