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
from krmod.ui.formatting import format_val
from krmod.ui.spinbox import SpinBox


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

# A section key is a row group, or SKILLS_KEY for the heading that folds all skill sections.
SKILLS_KEY = "*skills*"
_OPEN, _SHUT = "\u25be", "\u25b8"


def _section_keys(group: str) -> list[str]:
    """The group and its parent groups ("ultimate.burn" -> "ultimate", "ultimate.burn")."""
    parts = group.split(".") if group else []
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


class _Sections:
    """Shows and hides table rows when a section title is clicked.

    Folding a section also hides its sub-sections (Ultimate hides Ultimate / Burn); folding
    the Skills heading hides every skill section of the card.
    """

    def __init__(self, card_id: str, levels: int, folded: set[tuple[str, str]]) -> None:
        self.card_id = card_id
        self.levels = levels
        self._folded = folded  # (card id, section key), owned by the page
        self._rows: list[tuple[ui.element, str, bool]] = []  # row, group, is skill
        self._headers: list[tuple[ui.element, ui.label, str, bool]] = []  # row, arrow, key, is skill

    def folded(self, key: str) -> bool:
        return (self.card_id, key) in self._folded

    def header(self, key: str, text: str, is_skill: bool) -> None:
        """A clickable title row: a row group, or SKILLS_KEY for the Skills heading."""
        heading = key == SKILLS_KEY
        grp = (
            "bg-slate-200 border-t border-b border-slate-300 py-1.5" if heading
            else "bg-slate-100 border-t border-b border-slate-200 py-1"
        )
        tr = ui.element("tr").classes("cursor-pointer select-none")
        tr.mark("skills-heading" if heading else "section-" + key.replace(" ", "-").replace(".", "-"))
        with tr:
            with ui.element("td").classes(
                f"{grp} px-3 font-bold text-xs uppercase tracking-wider text-slate-600 {_PIN_L}"
            ):
                with ui.row().classes("items-center gap-1 no-wrap"):
                    arrow = ui.label(_SHUT if self.folded(key) else _OPEN).classes("w-3")
                    ui.label(text)
            ui.element("td").props(f"colspan={self.levels}").classes(grp)
            ui.element("td").classes(f"{grp} {_PIN_R}")
        tr.on("click", lambda _, k=key: self.toggle(k))
        self._headers.append((tr, arrow, key, is_skill and not heading))

    def row(self, tr: ui.element, group: str, is_skill: bool) -> None:
        self._rows.append((tr, group, is_skill))

    def toggle(self, key: str) -> None:
        self._folded.symmetric_difference_update({(self.card_id, key)})
        self.apply()

    def _hidden(self, group: str, is_skill: bool, parents_only: bool) -> bool:
        if is_skill and self.folded(SKILLS_KEY):
            return True
        keys = _section_keys(group)
        return any(self.folded(k) for k in (keys[:-1] if parents_only else keys))

    def apply(self) -> None:
        for tr, arrow, key, is_skill in self._headers:
            arrow.set_text(_SHUT if self.folded(key) else _OPEN)
            if key != SKILLS_KEY:
                tr.set_visibility(not self._hidden(key, is_skill, parents_only=True))
        for tr, group, is_skill in self._rows:
            tr.set_visibility(not self._hidden(group, is_skill, parents_only=False))


class CellController:
    """Controller for an editable numeric cell in the level table."""

    def __init__(self, state: AppState, path: KeyPath, on_change: Callable[[], None]) -> None:
        self.state = state
        self.path = path
        self.on_change = on_change

        self.box = SpinBox(
            format_val(state.current(path)),
            on_commit=self.commit,
            on_step=self.step,
            on_reset=self.reset,
            marker=f"cell-{path_str(path)}",
            classes="w-24",
        )
        self._decorate(state.current(path))

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
        """Re-read the cell; SpinBox only sends props that actually changed."""
        curr = self.state.current(self.path)
        self.box.set_text(format_val(curr))
        self._decorate(curr)

    def _decorate(self, curr: float) -> None:
        # The struck game value under a changed cell resets it; keeping it under the box (not
        # beside it) keeps changed and unchanged cells the same width.
        if self.state.is_changed(self.path):
            self.box.set_tone("changed")
            self.box.set_original(format_val(self.state.original(self.path)))
        else:
            self.box.set_tone(None)
            self.box.set_original(None)
        self.box.set_warning(warn(self.path, curr))


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


def render_card(
    state: AppState,
    card_id: str,
    right: ui.element,
    on_refresh: Callable[[], None],
    folded: set[tuple[str, str]],
) -> None:
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
                sections = _Sections(card_id, max_levels, folded)
                with ui.element("tbody"):
                    last_group: str | None = None
                    in_skills = False

                    for row in rows:
                        # The Skills heading above the first skill section:
                        if row.is_skill and not in_skills:
                            in_skills = True
                            sections.header(SKILLS_KEY, "Skills", True)
                        # Section title row when the group changes:
                        if row.group != last_group:
                            last_group = row.group
                            if row.group:
                                sections.header(row.group, friendly_group_label(row.group), row.is_skill)

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
                        with ui.element("tr").classes("group") as tr:
                            sections.row(tr, row.group, row.is_skill)
                            # Stat column (pinned left):
                            with ui.element("td").classes(f"{cell} px-3 {_PIN_L}"):
                                name_color = "text-slate-600" if row.read_only else "text-slate-800"
                                # A native title instead of a Quasar tooltip: one element less per row.
                                stat_lbl = ui.label(row.label).classes(
                                    f"font-medium {name_color} whitespace-nowrap"
                                )
                                stat_lbl._props["title"] = row.id
                                if alias_note:
                                    ui.label(alias_note).classes("text-xs text-amber-600 italic")

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
                                if not row.read_only and state.row_scalable(row):
                                    pct_boxes.append(
                                        PctBox(
                                            lambda r=row: state.row_pct(r),
                                            lambda pct, r=row: state.scale_row(r, pct),
                                            f"row-pct-{row_slug}",
                                            on_mutation,
                                            is_changed=lambda r=row: state.row_changed(r),
                                            reset=lambda r=row: state.reset_row(r),
                                        )
                                    )
                sections.apply()

        ui.run_javascript(_OVERFLOW_JS % scroller.id)
