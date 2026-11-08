"""Level table component: editable level cells, Row % boxes and quick scale boxes."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.model.rows import HERO_BARS_LABEL, StatRow
from krmod.model.scaling import warn
from krmod.model.stepping import step_cell
from krmod.model.values import KeyPath, decode_damage_type, path_str
from krmod.state import AppState
from krmod.ui.pctbox import PctBox
from krmod.ui.sliders import format_val
from krmod.ui.spinbox import SpinBox

_CHANGED_CLASSES = "bg-amber-100 border-amber-500 font-bold text-amber-900"

# The Stat column is pinned to the left edge and the Row % column to the right edge of the
# horizontal scroller. Pinned cells need an opaque background so levels slide underneath.
# The edge shadows show only while the table overflows (the wrapper gets .kr-overflow).
_PIN_L = "sticky left-0 z-10 kr-pin-l"
_PIN_R = "sticky right-0 z-10 kr-pin-r"
_SCROLLER = (
    "w-full overflow-x-auto "
    "[&.kr-overflow_.kr-pin-l]:shadow-[4px_0_6px_-4px_rgba(15,23,42,0.35)] "
    "[&.kr-overflow_.kr-pin-r]:shadow-[-4px_0_6px_-4px_rgba(15,23,42,0.35)]"
)
_OVERFLOW_JS = """
const el = getHtmlElement(%d);
if (el) {
  const f = () => el.classList.toggle('kr-overflow', el.scrollWidth > el.clientWidth + 1);
  const ro = new ResizeObserver(f);
  ro.observe(el);
  if (el.firstElementChild) ro.observe(el.firstElementChild);
  f();
}
"""


class CellController:
    """Controller for an editable numeric cell in the level table."""

    def __init__(self, state: AppState, path: KeyPath, on_change: Callable[[], None]) -> None:
        self.state = state
        self.path = path
        self.on_change = on_change

        curr = state.current(path)
        orig = state.original(path)
        is_chg = state.is_changed(path)

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

            self.box = SpinBox(
                format_val(curr),
                on_commit=self.commit,
                on_step=self.step,
                marker=f"cell-{p_str}",
                classes="w-28",
            )
            if is_chg:
                self.box.inp.classes(add=_CHANGED_CLASSES)

    def commit(self, text: str) -> None:
        success, err_or_warn = self.state.parse_and_set(self.path, text.strip())
        if not success:
            ui.notify(err_or_warn or "Not a number.", color="negative")
            self.box.set_text(format_val(self.state.current(self.path)))
            return
        if err_or_warn:
            ui.notify(err_or_warn, color="warning")
        self.on_change()

    def step(self, direction: int, shift: bool) -> None:
        new = step_cell(
            self.state.current(self.path), self.state.original(self.path), direction, shift
        )
        try:
            warning = self.state.set_value(self.path, new)
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            return
        if warning:
            ui.notify(warning, color="warning")
        self.on_change()

    def reset(self) -> None:
        self.state.reset(self.path)
        self.on_change()

    def refresh(self) -> None:
        curr = self.state.current(self.path)
        orig = self.state.original(self.path)
        is_chg = self.state.is_changed(self.path)
        self.box.set_text(format_val(curr))

        if is_chg:
            self.box.inp.classes(add=_CHANGED_CLASSES)
            self.orig_label.text = format_val(orig)
            self.orig_label.set_visibility(True)
            self.reset_btn.set_visibility(True)
        else:
            self.box.inp.classes(remove=_CHANGED_CLASSES)
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


def _read_only_text(state: AppState, p: KeyPath, row: StatRow) -> str:
    leaf = state.tree.leaves.get(p)
    if row.is_enum and leaf is not None:
        return decode_damage_type(int(leaf.value), state.tree.damage_flags)
    if leaf is not None and leaf.kind in ("str", "bool"):
        return str(leaf.value)
    if leaf is not None:
        return format_val(leaf.value)
    return ""


def render_card(state: AppState, card_id: str, right: ui.element, on_refresh: Callable[[], None]) -> None:
    """Render the quick scale boxes and the level table (cells and Row % boxes) into right.

    on_refresh updates the page chrome (top bar, cards column) after an edit.
    """

    rows = state.rows(card_id)
    max_levels = max((len(r.cells) for r in rows), default=1)

    all_cells: list[CellController] = []
    pct_boxes: list[PctBox] = []

    def on_mutation() -> None:
        for c in all_cells:
            c.refresh()
        for b in pct_boxes:
            b.refresh()
        on_refresh()

    with right:
        categories = state.card_categories(card_id)
        if categories:
            with ui.column().classes(
                "w-full bg-slate-50 border border-slate-200 rounded-lg p-3 gap-2 mb-3 shrink-0"
            ):
                with ui.row().classes("items-baseline justify-between w-full gap-x-3 gap-y-0"):
                    ui.label("Quick scale all levels").classes(
                        "text-xs font-semibold text-slate-500 uppercase tracking-wide"
                    )
                    ui.label("0% to 500%, type or use the arrows").classes("text-xs text-slate-400 italic")
                with ui.row().classes("w-full items-center gap-x-4 gap-y-2"):
                    for cat in categories:
                        with ui.row().classes("items-center gap-2 no-wrap"):
                            ui.label(cat).classes("text-xs font-medium text-slate-700 whitespace-nowrap")
                            pct_boxes.append(
                                PctBox(
                                    lambda c=cat: state.card_pct(card_id, c),
                                    lambda pct, c=cat: state.scale_card(card_id, c, pct),
                                    f"card-pct-{cat.replace(' ', '-').lower()}",
                                    on_mutation,
                                )
                            )

        scroller = ui.element("div").classes(_SCROLLER)
        with scroller:
            with ui.element("table").classes("min-w-full w-max border-separate border-spacing-0 text-left text-sm"):
                # Header:
                with ui.element("thead"):
                    with ui.element("tr").classes("text-xs font-semibold text-slate-500 uppercase tracking-wider"):
                        head = "bg-white border-b border-slate-200 py-2"
                        with ui.element("th").classes(f"{head} px-3 text-left {_PIN_L}"):
                            ui.label("Stat")
                        for i in range(max_levels):
                            col_title = f"Level {i + 1}" if max_levels > 1 else "Value"
                            with ui.element("th").classes(f"{head} px-2 text-right"):
                                ui.label(col_title)
                        with ui.element("th").classes(f"{head} px-3 text-right {_PIN_R}"):
                            ui.label("Row %")

                # Body:
                with ui.element("tbody"):
                    last_group: str | None = None

                    for row in rows:
                        # Group header row when group changes:
                        if row.group != last_group:
                            last_group = row.group
                            if row.group:
                                grp = "bg-slate-100 border-t border-b border-slate-200 py-1"
                                with ui.element("tr"):
                                    with ui.element("td").classes(
                                        f"{grp} px-3 font-bold text-xs uppercase tracking-wider text-slate-600 {_PIN_L}"
                                    ):
                                        ui.label(friendly_group_label(row.group))
                                    ui.element("td").props(f"colspan={max_levels}").classes(grp)
                                    ui.element("td").classes(f"{grp} {_PIN_R}")

                        row_slug = row.id.replace(" ", "-").replace(".", "-")

                        # Check for alias note:
                        alias_note: str | None = None
                        for p in row.cells:
                            if p is not None:
                                note = state.alias_note(p)
                                if note:
                                    alias_note = note
                                    break

                        cell = "py-1.5 border-b border-slate-100 bg-white group-hover:bg-slate-50"
                        with ui.element("tr").classes("group"):
                            # Stat column (pinned left):
                            with ui.element("td").classes(f"{cell} px-3 {_PIN_L}"):
                                name_color = "text-slate-600" if row.read_only else "text-slate-800"
                                with ui.row().classes("items-center gap-1.5 flex-nowrap"):
                                    stat_lbl = ui.label(row.label).classes(
                                        f"font-medium {name_color} whitespace-nowrap"
                                    )
                                    stat_lbl.tooltip(row.id)
                                    if alias_note:
                                        ui.label(alias_note).classes("text-xs text-amber-600 italic ml-1")

                            # Level columns:
                            for col_idx in range(max_levels):
                                with ui.element("td").classes(f"{cell} px-2 text-right"):
                                    if col_idx < len(row.cells) and row.cells[col_idx] is not None:
                                        p = row.cells[col_idx]
                                        assert p is not None
                                        if row.read_only:
                                            ui.label(_read_only_text(state, p, row)).classes(
                                                "text-sm text-slate-600 font-mono"
                                            )
                                        else:
                                            cell_ctrl = CellController(state, p, on_change=on_mutation)
                                            all_cells.append(cell_ctrl)

                            # Row % column (pinned right):
                            with ui.element("td").classes(f"{cell} px-3 text-right {_PIN_R}"):
                                if not row.read_only:
                                    with ui.row().classes("justify-end no-wrap"):
                                        pct_boxes.append(
                                            PctBox(
                                                lambda r=row: state.row_pct(r),
                                                lambda pct, r=row: state.scale_row(r, pct),
                                                f"row-pct-{row_slug}",
                                                on_mutation,
                                            )
                                        )

        ui.run_javascript(_OVERFLOW_JS % scroller.id)
