"""Left column component: search box and unit cards grouped by category."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.assets.portraits import portrait_for
from krmod.model.grouping import Card
from krmod.state import AppState


class CardsColumn:
    def __init__(
        self,
        state: AppState,
        on_card_click: Callable[[str], None],
    ) -> None:
        self.state = state
        self.on_card_click = on_card_click
        self.current_tab: str = "Towers"
        self.search_query: str = ""

        self.container: ui.column
        self.search_input: ui.input
        self.cards_area: ui.column

        self._build()

    def _build(self) -> None:
        self.container = ui.column().classes("w-80 h-full p-3 gap-2")
        with self.container:
            self.search_input = (
                ui.input(placeholder="Search…", on_change=lambda e: self.set_search(e.value or ""))
                .props("outlined dense clearable")
                .classes("w-full mb-1")
                .mark("card-search")
            )
            self.cards_area = ui.column().classes("w-full flex-1 overflow-y-auto gap-3")
            self._render_cards()

    def set_tab(self, tab: str) -> None:
        self.current_tab = tab
        self._render_cards()

    def set_search(self, query: str) -> None:
        self.search_query = query.strip().lower()
        self._render_cards()

    def refresh(self) -> None:
        self._render_cards()

    def _render_cards(self) -> None:
        self.cards_area.clear()
        if self.current_tab == "Rules":
            return

        all_cards = self.state.index.cards(self.current_tab)  # type: ignore[arg-type]
        if self.search_query:
            cards = [c for c in all_cards if self.search_query in c.title.lower()]
        else:
            cards = all_cards

        # Group cards by card.group preserving order:
        grouped: dict[str, list[Card]] = {}
        for card in cards:
            grouped.setdefault(card.group, []).append(card)

        with self.cards_area:
            if not grouped:
                ui.label("No matching units").classes("text-xs text-slate-400 italic px-2 py-4")
                return

            for group_name, group_cards in grouped.items():
                with ui.column().classes("w-full gap-1"):
                    ui.label(group_name).classes(
                        "text-[11px] font-bold text-slate-500 uppercase tracking-wider px-1 mt-1"
                    )
                    with ui.column().classes("w-full gap-1.5"):
                        for card in group_cards:
                            self._build_card_tile(card)

    def _build_card_tile(self, card: Card) -> None:
        has_changes = self.state.card_has_changes(card.id)
        card_id = card.id

        tile = ui.row().classes(
            "w-full items-center p-2 rounded-lg border border-slate-200 hover:border-blue-400 hover:bg-blue-50/50 cursor-pointer transition-all gap-2.5 bg-white shadow-sm"
        ).mark(f"card-{card.id} {card.title}")
        tile.on("click", lambda _e, cid=card_id: self.on_card_click(cid))

        with tile:
            # Portrait or initials fallback
            portrait_path = portrait_for(card.id, self.state.paths.cache_dir)
            if portrait_path and portrait_path.is_file():
                ui.image(str(portrait_path)).classes("w-10 h-10 rounded object-cover shadow-xs")
            else:
                with ui.element("div").classes(
                    "w-10 h-10 rounded bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-500 text-xs shrink-0"
                ):
                    ui.label(card.title[:2].upper())

            # Card title
            ui.label(card.title).classes("text-sm font-semibold text-slate-800 flex-1 truncate")

            # Dot indicator for changed values
            if has_changes:
                ui.label("●").classes("text-amber-500 font-bold text-sm")
