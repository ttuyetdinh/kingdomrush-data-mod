"""Left column component: search box and unit cards grouped by category."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from krmod.assets.portraits import portrait_for
from krmod.model.grouping import Card
from krmod.state import AppState
from krmod.ui.portrait import portrait_img


class CardsColumn:
    def __init__(
        self,
        state: AppState,
        on_card_click: Callable[[str], None],
        folded: bool = False,
        on_fold_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.state = state
        self.on_card_click = on_card_click
        self.on_fold_change = on_fold_change
        self.current_tab: str = "Towers"
        self.search_query: str = ""
        self.folded = folded

        self.container: ui.column
        self.strip: ui.column
        self.search_input: ui.input
        self.cards_area: ui.column
        self._dots: dict[str, ui.label] = {}

        self._build()

    def _build(self) -> None:
        self.container = ui.column().classes("w-80 h-full p-0 gap-0 overflow-hidden min-h-0 flex-nowrap")
        with self.container:
            with ui.row().classes("w-full p-3 pb-2 shrink-0 items-center gap-1 flex-nowrap"):
                self.search_input = (
                    ui.input(placeholder="Search…", on_change=lambda e: self.set_search(e.value or ""))
                    .props("outlined dense clearable")
                    .classes("flex-1 min-w-0")
                    .mark("card-search")
                )
                ui.button("«", on_click=lambda: self.set_folded(True)).props(
                    "flat dense no-caps color=secondary"
                ).classes("shrink-0").mark("cards-fold").tooltip("Fold the card list")
            self.cards_area = ui.column().classes("w-full flex-1 overflow-y-auto px-3 pb-3 gap-3 min-h-0")
            self._render_cards()
        self.strip = ui.column().classes("w-[26px] h-full p-0 pt-3 items-center shrink-0")
        with self.strip:
            ui.button("»", on_click=lambda: self.set_folded(False)).props(
                "flat dense no-caps color=secondary"
            ).classes("w-full").mark("cards-unfold").tooltip("Unfold the card list")
        self._apply_folded()

    def set_folded(self, folded: bool) -> None:
        self.folded = folded
        self._apply_folded()
        if self.on_fold_change is not None:
            self.on_fold_change(folded)

    def _apply_folded(self) -> None:
        self.container.set_visibility(not self.folded)
        self.strip.set_visibility(self.folded)

    def set_tab(self, tab: str) -> None:
        self.current_tab = tab
        self._render_cards()

    def set_search(self, query: str) -> None:
        self.search_query = query.strip().lower()
        self._render_cards()

    def refresh(self) -> None:
        """After an edit: update the changed dots in place. Rebuilding the tiles would reload
        every portrait and reset the list's scroll position."""
        for card_id, dot in self._dots.items():
            dot.set_visibility(self.state.card_has_changes(card_id))

    def _render_cards(self) -> None:
        self.cards_area.clear()
        self._dots = {}
        if self.current_tab == "Rules":
            return

        all_cards = self.state.index.cards(self.current_tab)  # type: ignore[arg-type]
        if self.search_query:
            # The game's name or the data name in the card id (search "archers" finds Archer Garrison).
            cards = [
                c for c in all_cards
                if self.search_query in c.title.lower() or self.search_query in c.id.replace("_", " ")
            ]
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
            portrait_path = portrait_for(card.id, self.state.paths.portraits_dir)
            if portrait_path and portrait_path.is_file():
                # Lazy plain <img>: a tab can list hundreds of units.
                portrait_img(portrait_path, "w-10 h-10 rounded object-cover shadow-xs shrink-0", lazy=True)
            else:
                with ui.element("div").classes(
                    "w-10 h-10 rounded bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-500 text-xs shrink-0"
                ):
                    ui.label(card.title[:2].upper())

            # Card title
            ui.label(card.title).classes("text-sm font-semibold text-slate-800 flex-1 truncate")

            # Dot indicator for changed values; refresh() only toggles it.
            dot = ui.label("●").classes("text-amber-500 font-bold text-sm").mark(f"card-dot-{card.id}")
            dot.set_visibility(has_changes)
            self._dots[card_id] = dot
