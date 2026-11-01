"""Level table component for editing stat rows with C1 and C2 sliders."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.model.rows import HERO_BARS_LABEL, StatRow
from krmod.model.scaling import warn
from krmod.model.values import KeyPath, decode_damage_type, path_str
from krmod.state import AppState
from krmod.ui.sliders import (
    C2Panel,
    CardSliders,
    RowSlider,
    format_val,
)


class CellController:
    """Controller for an editable numeric cell in the level table."""

    def __init__(self, state: AppState, path: KeyPath, on_change: Callable[[], None]) -> None:
        self.state = state
        self.path = path
        self.on_change = on_change

        curr = state.current(path)
        orig = state.original(path)
        is_chg = state.is_changed(path)
        val_str = format_val(curr)
        self.last_committed = val_str

        p_str = path_str(path)
        with ui.row().classes("items-center justify-end gap-1 no-wrap"):
            self.warn_icon = (
                ui.icon("warning", color="warning", size="xs")
                .classes("cursor-pointer")
                .mark(f"warn-{p_str}")
            )
            w = warn(path, curr)
            with self.warn_icon:
                self.warn_tooltip = ui.tooltip(w or "")
            self.warn_icon.set_visibility(bool(w))

            self.orig_label = (
                ui.label(format_val(orig))
                .classes("text-xs text-slate-400 line-through")
                .mark(f"orig-{p_str}")
            )
            self.orig_label.set_visibility(is_chg)

            self.reset_btn = (
                ui.button(icon="undo", on_click=self.reset)
                .props("flat dense round size=xs")
                .classes("text-slate-400 hover:text-slate-700")
                .mark(f"reset-{p_str}")
            )
            self.reset_btn.set_visibility(is_chg)

            self.inp = (
                ui.input(value=val_str)
                .props("dense outlined")
                .classes("w-20 font-mono text-sm text-right")
                .mark(f"cell-{p_str}")
            )
            if is_chg:
                self.inp.classes(add="bg-amber-100 border-amber-500 font-bold text-amber-900")

            self.inp.on("keydown.enter", self.commit)
            self.inp.on("blur", self.commit)

    def commit(self) -> None:
        text = str(self.inp.value or "").strip()
        if text == self.last_committed:
            return
        success, err_or_warn = self.state.parse_and_set(self.path, text)
        if not success:
            reason = err_or_warn or "Not a number."
            ui.notify(reason, color="negative")
            self.inp.value = format_val(self.state.current(self.path))
            self.last_committed = self.inp.value
            return
        if err_or_warn:
            ui.notify(err_or_warn, color="warning")
        self.last_committed = format_val(self.state.current(self.path))
        self.on_change()

    def reset(self) -> None:
        self.state.reset(self.path)
        self.last_committed = format_val(self.state.current(self.path))
        self.inp.value = self.last_committed
        self.on_change()

    def refresh(self) -> None:
        curr = self.state.current(self.path)
        orig = self.state.original(self.path)
        is_chg = self.state.is_changed(self.path)
        val_str = format_val(curr)
        self.inp.value = val_str
        self.last_committed = val_str

        if is_chg:
            self.inp.classes(add="bg-amber-100 border-amber-500 font-bold text-amber-900")
            self.orig_label.text = format_val(orig)
            self.orig_label.set_visibility(True)
            self.reset_btn.set_visibility(True)
        else:
            self.inp.classes(remove="bg-amber-100 border-amber-500 font-bold text-amber-900")
            self.orig_label.set_visibility(False)
            self.reset_btn.set_visibility(False)

        w = warn(self.path, curr)
        self.warn_icon.set_visibility(bool(w))
        if w:
            self.warn_tooltip.set_text(w)


def friendly_group_label(group: str) -> str:
    """Format StatRow.group into friendly heading text."""
    if not group:
        return ""
    if group == HERO_BARS_LABEL:
        return HERO_BARS_LABEL
    parts = [p.replace("_", " ").capitalize() for p in group.split(".")]
    return " / ".join(parts) if len(parts) > 1 else parts[0]


def render_card(state: AppState, card_id: str) -> None:
    """Render card's C1 card sliders, level table, row sliders, and C2 panels."""
    from krmod.ui import main as ui_main

    right = ui_main.REGIONS.get("right")
    if right is None:
        return

    rows = state.rows(card_id)
    max_levels = max((len(r.cells) for r in rows), default=1)

    all_cells: list[CellController] = []
    all_row_sliders: list[RowSlider] = []
    c2_panels: list[C2Panel] = []

    def on_mutation() -> None:
        for c in all_cells:
            c.refresh()
        for rs in all_row_sliders:
            rs.refresh()
        card_sliders.refresh()
        for p in c2_panels:
            p.refresh()
        ui_main.refresh()

    with right:
        card_sliders = CardSliders(state, card_id, on_change=on_mutation)

        with ui.column().classes("w-full overflow-x-auto"):
            with ui.element("table").classes("w-full border-collapse text-left text-sm"):
                # Header:
                with ui.element("thead"):
                    with ui.element("tr").classes(
                        "border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider"
                    ):
                        with ui.element("th").classes("py-2 px-3 text-left"):
                            ui.label("Stat")
                        for i in range(max_levels):
                            col_title = f"Level {i + 1}" if max_levels > 1 else "Value"
                            with ui.element("th").classes("py-2 px-2 text-right"):
                                ui.label(col_title)
                        with ui.element("th").classes("py-2 px-3 text-right w-44"):
                            ui.label("Row slider")

                # Body:
                with ui.element("tbody"):
                    last_group: str | None = None

                    for row in rows:
                        # Group header row when group changes:
                        if row.group != last_group:
                            last_group = row.group
                            if row.group:
                                grp_name = friendly_group_label(row.group)
                                with ui.element("tr").classes("bg-slate-100/90 border-t border-b border-slate-200"):
                                    with ui.element("td").props(f"colspan={1 + max_levels + 1}").classes(
                                        "py-1 px-3 font-bold text-xs uppercase tracking-wider text-slate-600"
                                    ):
                                        ui.label(grp_name)

                        row_slug = row.id.replace(" ", "-").replace(".", "-")

                        # Check for alias note:
                        alias_note: str | None = None
                        for p in row.cells:
                            if p is not None:
                                note = state.alias_note(p)
                                if note:
                                    alias_note = note
                                    break

                        # Main stat row:
                        with ui.element("tr").classes("border-b border-slate-100 hover:bg-slate-50/50"):
                            # Stat column:
                            with ui.element("td").classes("py-1.5 px-3"):
                                if not row.read_only:
                                    c2_row_ref: list[ui.element | None] = [None]
                                    c2_panel_ref: list[C2Panel | None] = [None]
                                    chevron_ref: list[ui.label | None] = [None]

                                    def make_toggle(
                                        c_row_ref=c2_row_ref,
                                        p_ref=c2_panel_ref,
                                        ch_ref=chevron_ref,
                                        r=row,
                                    ):
                                        def toggle():
                                            c_row = c_row_ref[0]
                                            ch = ch_ref[0]
                                            if c_row is None:
                                                return
                                            if p_ref[0] is None:
                                                # Build C2 panel lazily
                                                c_container = c_row.default_slot.children[0].default_slot.children[0]
                                                panel = C2Panel(state, r, on_change=on_mutation, container=c_container)
                                                p_ref[0] = panel
                                                c2_panels.append(panel)
                                                c_row.set_visibility(True)
                                                if ch is not None:
                                                    ch.text = "▾"
                                            else:
                                                is_vis = not c_row.visible
                                                c_row.set_visibility(is_vis)
                                                if ch is not None:
                                                    ch.text = "▾" if is_vis else "▸"
                                                if is_vis:
                                                    p_ref[0].refresh()
                                        return toggle

                                    with ui.row().classes(
                                        "items-center gap-1.5 cursor-pointer select-none"
                                    ).mark(f"row-expand-{row_slug}").on("click", make_toggle()):
                                        ch_lbl = ui.label("▸").classes("text-slate-400 font-mono text-xs w-3")
                                        chevron_ref[0] = ch_lbl
                                        ui.label(row.label).classes("font-medium text-slate-800")
                                        if alias_note:
                                            ui.label(alias_note).classes("text-xs text-amber-600 italic ml-1")
                                else:
                                    with ui.row().classes("items-center gap-1.5"):
                                        ui.label(" ").classes("w-3")
                                        ui.label(row.label).classes("font-medium text-slate-600")
                                        if alias_note:
                                            ui.label(alias_note).classes("text-xs text-amber-600 italic ml-1")

                            # Level columns:
                            for col_idx in range(max_levels):
                                with ui.element("td").classes("py-1.5 px-2 text-right"):
                                    if col_idx < len(row.cells) and row.cells[col_idx] is not None:
                                        p = row.cells[col_idx]
                                        assert p is not None
                                        if row.read_only:
                                            leaf = state.tree.leaves.get(p)
                                            if row.is_enum and leaf is not None:
                                                text = decode_damage_type(int(leaf.value), state.tree.damage_flags)
                                            elif leaf is not None and leaf.kind in ("str", "bool"):
                                                text = str(leaf.value)
                                            elif leaf is not None:
                                                text = format_val(leaf.value)
                                            else:
                                                text = ""
                                            ui.label(text).classes("text-sm text-slate-600 font-mono")
                                        else:
                                            cell_ctrl = CellController(state, p, on_change=on_mutation)
                                            all_cells.append(cell_ctrl)
                                    else:
                                        pass

                            # Row slider column:
                            with ui.element("td").classes("py-1.5 px-3 text-right"):
                                if not row.read_only:
                                    row_slider = RowSlider(state, row, on_change=on_mutation)
                                    all_row_sliders.append(row_slider)

                        # C2 Panel row (collapsed initially):
                        if not row.read_only:
                            c2_row = ui.element("tr").classes("bg-slate-50 border-b border-slate-200")
                            c2_row.set_visibility(False)
                            c2_row_ref[0] = c2_row
                            with c2_row:
                                with ui.element("td").props(f"colspan={1 + max_levels + 1}").classes("p-3"):
                                    ui.column().classes("w-full gap-2")
