"""Rules tab view: unlock switches, extra points, speed key bindings, live Enemies and Troops
boxes, and stale changes."""
from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from krmod.model.stepping import EXTRA_POINTS_MAX, clamp_points, parse_number, step_points
from krmod.model.values import path_str
from krmod.profiles import FORBIDDEN_KEYS, ProfileError, validate_speed_keys
from krmod.state import AppState
from krmod.ui.livebox import LiveBox
from krmod.ui.spinbox import SpinBox

# Switches for the game's star locks: label, profile rule, marker, game screen.
_STAR_UNLOCKS = (
    ("Unlock all heroes", "unlock_heroes", "unlock-heroes-switch", "hero room"),
    ("Unlock all towers", "unlock_towers", "unlock-towers-switch", "tower room"),
    ("Unlock all spells", "unlock_spells", "unlock-spells-switch", "spell room"),
)


class PointsBox:
    """A label and a SpinBox bound to one extra points rule of the active profile.

    Typed numbers are rounded and clamped to 0..EXTRA_POINTS_MAX; the arrows step 1 (10 with
    Shift). Every accepted value goes through state.set_rule, which saves the profile.
    """

    def __init__(self, state: AppState, rule: str, label: str, marker: str) -> None:
        self.state = state
        self.rule = rule
        with ui.row().classes("items-center gap-2 flex-nowrap"):
            ui.label(label).classes("text-sm text-slate-700 w-44")
            self.box = SpinBox(
                str(self._current()),
                on_commit=self._on_commit,
                on_step=lambda direction, shift: self._save(
                    step_points(self._current(), direction, shift)
                ),
                marker=marker,
                classes="w-20",
            )

    def _current(self) -> int:
        return getattr(self.state.profile, self.rule)

    def _on_commit(self, text: str) -> None:
        try:
            typed = parse_number(text)
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            self.box.set_text(str(self._current()))
            return
        self._save(clamp_points(typed))

    def _save(self, value: int) -> None:
        if value != self._current():
            try:
                self.state.set_rule(self.rule, value)
            except ProfileError as exc:
                ui.notify(str(exc), color="negative")
        self.box.set_text(str(self._current()))


def render(state: AppState, on_refresh: Callable[[], None]) -> None:
    """Render Rules tab content in the right editor region."""
    with ui.column().classes("w-full max-w-3xl p-6 gap-6 shrink-0"):
        # Header
        with ui.column().classes("gap-1"):
            ui.label("Rules & Global Settings").classes(
                "text-2xl font-bold text-slate-900"
            ).mark("rules-title")
            ui.label(
                "Game-wide rules, hotkeys, and live game controls"
            ).classes("text-sm text-slate-500")

        # Section 1: Progression Rules
        with ui.card().classes(
            "w-full p-4 border border-slate-200 shadow-sm rounded-lg"
        ):
            ui.label("Progression Rules").classes(
                "text-base font-semibold text-slate-800 mb-2"
            )
            ui.switch(
                "Unlock all tower levels",
                value=state.profile.unlock_tower_levels,
                on_change=lambda e: state.set_rule("unlock_tower_levels", bool(e.value)),
            ).mark("unlock-switch")
            ui.label(
                "Removes the upgrade level limit of towers inside every stage."
            ).classes("text-xs text-slate-400 mt-1")
            for label, rule, marker, room in _STAR_UNLOCKS:
                ui.switch(
                    label,
                    value=getattr(state.profile, rule),
                    on_change=lambda e, rule=rule: state.set_rule(rule, bool(e.value)),
                ).mark(marker).classes("mt-3")
                ui.label(
                    f"Everything in the {room} is available without collecting stars. No unlock is "
                    "written to your save: turn it off and the star requirements come back."
                ).classes("text-xs text-slate-400 mt-1")
            with ui.column().classes("gap-1 mt-4"):
                PointsBox(state, "extra_hero_points", "Extra hero skill points", "extra-hero-points")
                PointsBox(state, "extra_spell_points", "Extra spell skill points", "extra-spell-points")
                PointsBox(state, "extra_upgrade_points", "Extra skill tree points", "extra-upgrade-points")
            ui.label(
                f"Added on top of the game's points (0 to {EXTRA_POINTS_MAX}) for every hero, every "
                "spell and the skill tree: hero levels, spell levels and finished stages still give "
                "their normal points. If you lower a number after spending, use the game's reset "
                "button to get the points back."
            ).classes("text-xs text-slate-400 mt-1")
            ui.label(
                "Unlocks and extra points show the next time the map screen opens, after Apply mod."
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

        # Section 3: Live controls
        with ui.card().classes(
            "w-full p-4 border border-slate-200 shadow-sm rounded-lg gap-4"
        ):
            ui.label("Live Controls").classes(
                "text-base font-semibold text-slate-800"
            )
            ui.label(
                "Mirrors the top bar. Both take effect in the running game right away."
            ).classes("text-xs text-slate-500")

            # Enemy multiplier
            with ui.column().classes("w-full gap-1"):
                LiveBox(state, "enemy_mult", "rules-enemy-mult", on_refresh)
                ui.label(
                    "Multiplies regular enemies: 1 is the default, 0.25 spawns a quarter of "
                    "them, 10 spawns ten times as many. Bosses always spawn once."
                ).classes("text-xs text-slate-500")

            # Troop count
            with ui.column().classes("w-full gap-1"):
                LiveBox(state, "troop_delta", "rules-troop-delta", on_refresh)
                ui.label(
                    "Adds or removes soldiers per barracks, from -10 to +10: 0 is the default, "
                    "+1 is one more, -1 is one fewer. A large minus can leave a barracks empty."
                ).classes("text-xs text-slate-500")
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
