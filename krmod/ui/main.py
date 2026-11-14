"""UI shell page builder: window layout, top bar, left cards, right editor and bottom bar."""
from __future__ import annotations

import time
from pathlib import Path

from nicegui import run, ui

from krmod.assets.portraits import portrait_for
from krmod.gamedata.reader import ReaderError
from krmod.gameload import open_game_dir
from krmod.paths import (
    GameNotFoundError,
    default_repo_dir,
    load_cards_folded,
    save_cards_folded,
    save_game_dir_setting,
)
from krmod.profiles import ProfileStore
from krmod.state import AppState
from krmod.ui import applybar, gamefolder, rules, table
from krmod.ui.cards import CardsColumn
from krmod.ui.portrait import portrait_img
from krmod.ui.topbar import TopBar

# Process-wide state: one AppState serves every page (window or browser tab).
_active_state: AppState | None = None
_current_error: str | None = None
_repo_dir: Path | None = None


class Shell:
    """One built page: its regions, top bar, cards column, current tab and open card.

    NiceGUI builds the page once per client, so every handler has to render into the
    page that was clicked, never into the page that was built last.
    """

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.current_tab: str = "Towers"
        self.active_card_id: str | None = None
        # Folded table sections, (card id, section key), kept while this page lives.
        self.folded: set[tuple[str, str]] = set()
        self.topbar: TopBar
        self.cards_col: CardsColumn
        self.left_col: ui.element
        self.right_col: ui.element
        self.bottom_bar: ui.element

    def show_card(self, card_id: str) -> None:
        """Open card in the right editor region."""
        self.active_card_id = card_id
        card = self.state.index.card(card_id)
        self.right_col.clear()
        with self.right_col:
            portrait = portrait_for(card.id, self.state.paths.portraits_dir)
            with ui.row().classes("items-center gap-4 mb-4 shrink-0"):
                if portrait and portrait.is_file():
                    portrait_img(portrait, "w-14 h-14 rounded-lg shadow-sm object-cover")
                else:
                    with ui.element("div").classes(
                        "w-14 h-14 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-500 text-lg"
                    ):
                        ui.label(card.title[:2].upper())
                with ui.column().classes("gap-0.5"):
                    ui.label(card.title).classes("text-2xl font-bold text-slate-900").mark("editor-title")

        table.render_card(self.state, card_id, self.right_col, self.refresh, self.folded)

    def rerender_right(self) -> None:
        """Re-render the right editor region: Rules if on Rules tab, else active card or placeholder."""
        if self.current_tab == "Rules":
            self.right_col.clear()
            with self.right_col:
                rules.render(self.state, self.refresh)
        elif self.active_card_id is not None:
            self.show_card(self.active_card_id)
        else:
            self.right_col.clear()
            with self.right_col:
                self._placeholder()

    def refresh(self) -> None:
        """Update the top bar and cards column after a state mutation."""
        self.topbar.refresh()
        self.cards_col.refresh()
        if self.current_tab == "Rules":
            self.rerender_right()

    def on_tab_change(self, tab: str) -> None:
        self.current_tab = tab
        self.cards_col.set_tab(tab)
        self.rerender_right()

    def on_profile_change(self) -> None:
        """Profile switched, or all changes reset: re-render the editor unless on Rules."""
        self.refresh()
        if self.current_tab != "Rules":
            self.rerender_right()

    @staticmethod
    def _placeholder() -> None:
        with ui.column().classes("w-full h-full items-center justify-center text-center p-8"):
            ui.label("Select a unit on the left to edit stats").classes(
                "text-slate-400 italic text-base"
            )

    def build(self) -> None:
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
        # Style layout containers to prevent whole-page scrolling and enable independent scrolling
        ui.query("html, body").classes("h-full overflow-hidden").style("height: 100%; overflow: hidden;")
        ui.query(".q-page-container").classes("h-screen box-border overflow-hidden").style("height: 100vh; box-sizing: border-box; overflow: hidden;")
        ui.query(".q-page").classes("h-full max-h-full overflow-hidden").style("height: 100%; max-height: 100%; overflow: hidden;")
        ui.query(".nicegui-content").classes("h-full max-h-full p-0 gap-0 overflow-hidden").style("height: 100%; max-height: 100%; padding: 0; gap: 0; overflow: hidden;")

        self.topbar = TopBar(
            self.state,
            on_tab_change=self.on_tab_change,
            on_profile_change=self.on_profile_change,
            on_game_dir=use_game_folder,
            on_refresh=self.refresh,
        )

        # Main content area (left cards column + right editor column). Only the editor scrolls:
        # the top bar above and the bottom bar below stay in view on a short window.
        with ui.element("div").classes("w-full h-full flex flex-row overflow-hidden min-h-0"):
            self.left_col = ui.column().classes(
                "h-full border-r border-slate-200 bg-slate-50/50 p-0 gap-0 overflow-hidden shrink-0 min-h-0"
            )
            with self.left_col:
                self.cards_col = CardsColumn(
                    self.state,
                    on_card_click=self.show_card,
                    folded=load_cards_folded(_repo_dir or default_repo_dir()),
                    on_fold_change=self._save_cards_folded,
                )

            self.right_col = ui.column().classes("flex-1 min-w-0 h-full p-6 overflow-y-auto bg-white min-h-0 [&>*]:shrink-0")
            with self.right_col:
                self._placeholder()

        self.bottom_bar = ui.footer().classes("w-full items-center justify-between px-6 py-2 border-t border-slate-200 bg-slate-50 text-slate-800 shrink-0")
        with self.bottom_bar:
            applybar.render(self.state, self.refresh, self.on_profile_change)

    @staticmethod
    def _save_cards_folded(folded: bool) -> None:
        try:
            save_cards_folded(_repo_dir or default_repo_dir(), folded)
        except OSError as exc:
            ui.notify(f"Could not save the card list state: {exc}", color="negative")


async def use_game_folder(text: str) -> bool:
    """Validate and read a chosen game folder, save it, then reload the page so it shows the editor.

    With an active state this switches it to the new folder (profile and changes are kept);
    without one (startup error) it builds the state first. An invalid folder only notifies and
    returns False.
    """
    global _active_state, _current_error
    repo_dir = _repo_dir or default_repo_dir()
    raw = text.strip().strip('"')
    if not raw:
        ui.notify("Enter the path of the game folder.", color="negative")
        return False
    try:
        # Reading the balance data takes a moment: keep it off the event loop.
        loaded = await run.io_bound(open_game_dir, Path(raw).expanduser().resolve(), repo_dir)
        if loaded is None:  # the app is shutting down
            return False
        paths, tree, index = loaded
        save_game_dir_setting(repo_dir, paths.game_dir)
    except (GameNotFoundError, ReaderError, OSError) as exc:
        ui.notify(str(exc), color="negative")
        return False
    if _active_state is None:
        _active_state = AppState(paths, tree, index, ProfileStore(paths.profiles_dir))
        _current_error = None
    else:
        _active_state.switch_game(paths, tree, index)
    ui.navigate.reload()
    return True


def _render_error(error_msg: str) -> None:
    with ui.column().classes("w-full h-screen items-center justify-center p-8 bg-slate-900 text-white gap-4"):
        ui.icon("error", size="4rem", color="negative")
        ui.label("Error starting KrGenesis Mod").classes("text-2xl font-bold text-white")
        ui.label(error_msg).classes("text-sm text-red-300 max-w-xl text-center font-mono bg-slate-800 p-4 rounded-lg border border-red-500/30")
        with ui.card().classes("w-full max-w-xl gap-2"):
            ui.label("Select the folder that contains Kingdom Rush Genesis.exe").classes("text-sm text-slate-700")
            note = gamefolder.env_override_note()
            if note:
                ui.label(note).classes("text-xs text-amber-700")
            gamefolder.render_chooser(str((_repo_dir or default_repo_dir()).parent), use_game_folder)


def _render_page(state: AppState | None, error: str | None) -> None:
    if error is not None or state is None:
        _render_error(error or "Application state unavailable")
    else:
        Shell(state).build()


def build_page(state: AppState | None, error: str | None, repo_dir: Path | None = None) -> None:
    """Build the page layout registered on '/'."""
    global _active_state, _current_error, _repo_dir
    _active_state = state
    _current_error = error
    _repo_dir = repo_dir

    @ui.page("/")
    def index_page():
        # In the exe this goes to cache\app.log: one build per connect means a healthy page.
        print(f"{time.strftime('%H:%M:%S')} page built {ui.context.client.id}")
        _render_page(_active_state, _current_error)
