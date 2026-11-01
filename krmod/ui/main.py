"""UI shell page builder: window layout, top bar, left cards, right editor and bottom bar."""
from __future__ import annotations

from nicegui import ui

from krmod.assets.portraits import portrait_for
from krmod.state import AppState
from krmod.ui import applybar, rules, table
from krmod.ui.cards import CardsColumn
from krmod.ui.topbar import TopBar

# Public module-level regions dictionary for Tasks 12-13:
REGIONS: dict[str, ui.element] = {}

# Internal state references:
_active_state: AppState | None = None
_current_error: str | None = None
_topbar: TopBar | None = None
_cards_col: CardsColumn | None = None
_active_card_id: str | None = None
_current_tab: str = "Towers"


def show_card(card_id: str) -> None:
    """Open card in right editor region."""
    global _active_card_id
    _active_card_id = card_id

    right = REGIONS.get("right")
    if right is None or _active_state is None:
        return

    card = _active_state.index.card(card_id)
    right.clear()
    with right:
        with ui.row().classes("items-center gap-4 mb-4"):
            portrait = portrait_for(card.id, _active_state.paths.cache_dir)
            if portrait and portrait.is_file():
                ui.image(str(portrait)).classes("w-14 h-14 rounded-lg shadow-sm")
            else:
                with ui.element("div").classes(
                    "w-14 h-14 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-500 text-lg"
                ):
                    ui.label(card.title[:2].upper())
            with ui.column().classes("gap-0.5"):
                ui.label(card.title).classes("text-2xl font-bold text-slate-900").mark("editor-title")

    table.render_card(_active_state, card_id)


def rerender_right() -> None:
    """Re-render the right editor region: Rules if on Rules tab, else active card or placeholder."""
    if _active_state is None:
        return
    right = REGIONS.get("right")
    if right is None:
        return
    if _current_tab == "Rules":
        right.clear()
        with right:
            rules.render(_active_state)
    elif _active_card_id is not None:
        show_card(_active_card_id)
    else:
        right.clear()
        with right:
            ui.label("Select a unit on the left to edit stats").classes(
                "text-slate-400 italic mt-4"
            )


def refresh() -> None:
    """Module-level refresh hook for UI updates after state mutations."""
    if _topbar is not None:
        _topbar.refresh()
    if _cards_col is not None:
        _cards_col.refresh()
    rerender_right()
def _render_error(error_msg: str) -> None:
    with ui.column().classes("w-full h-screen items-center justify-center p-8 bg-slate-900 text-white gap-4"):
        ui.icon("error", size="4rem", color="negative")
        ui.label("Error starting KrGenesis Mod").classes("text-2xl font-bold text-white")
        ui.label(error_msg).classes("text-sm text-red-300 max-w-xl text-center font-mono bg-slate-800 p-4 rounded-lg border border-red-500/30")


def _render_shell(state: AppState) -> None:
    global _topbar, _cards_col, _active_state, _current_tab, _active_card_id
    _active_state = state
    _current_tab = "Towers"
    _active_card_id = None

    ui.colors(
        primary="#2563eb",
        secondary="#64748b",
        accent="#10b981",
        dark="#0f172a",
        positive="#16a34a",
        negative="#dc2626",
        info="#0284c7",
        warning="#d97706",
    )

    def on_tab_change(tab: str) -> None:
        global _current_tab
        _current_tab = tab
        if _cards_col is not None:
            _cards_col.set_tab(tab)
        rerender_right()

    def on_profile_change() -> None:
        refresh()

    # Top Bar
    _topbar = TopBar(state, on_tab_change=on_tab_change, on_profile_change=on_profile_change)
    REGIONS["topbar_right"] = _topbar.topbar_right

    # Main content area (left cards column + right editor column)
    with ui.element("div").classes("w-full flex-1 flex flex-row overflow-hidden"):
        # Left column
        left_col = ui.column().classes("h-full border-r border-slate-200 bg-slate-50/50 p-0 overflow-hidden shrink-0")
        REGIONS["left"] = left_col
        with left_col:
            _cards_col = CardsColumn(state, on_card_click=show_card)

        # Right editor column
        right_col = ui.column().classes("flex-1 h-full p-6 overflow-y-auto bg-white")
        REGIONS["right"] = right_col
        with right_col:
            ui.label("Select a unit on the left to edit stats").classes("text-slate-400 italic mt-4")

    # Bottom bar container
    bottom_bar = ui.footer().classes("w-full items-center justify-between px-6 py-2 border-t border-slate-200 bg-slate-50 text-slate-800 shrink-0")
    REGIONS["bottom"] = bottom_bar
    with bottom_bar:
        applybar.render(state)


def _render_page(state: AppState | None, error: str | None) -> None:
    if error is not None or state is None:
        _render_error(error or "Application state unavailable")
    else:
        _render_shell(state)


def build_page(state: AppState | None, error: str | None) -> None:
    """Build the page layout registered on '/'."""
    global _active_state, _current_error
    _active_state = state
    _current_error = error

    @ui.page("/")
    def index_page():
        _render_page(_active_state, _current_error)
