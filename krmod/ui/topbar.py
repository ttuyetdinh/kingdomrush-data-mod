"""Top bar component: app title, tabs, self-check, profile selector and change count."""
from __future__ import annotations

from typing import Callable

from nicegui import ui

UI_TABS: tuple[str, ...] = (
    "Towers", "Troops", "Heroes", "Skills", "Enemies", "Items", "Stages", "Rules"
)
from krmod.profiles import ProfileError
from krmod.state import AppState


class TopBar:
    def __init__(
        self,
        state: AppState,
        on_tab_change: Callable[[str], None],
        on_profile_change: Callable[[], None],
    ) -> None:
        self.state = state
        self.on_tab_change = on_tab_change
        self.on_profile_change = on_profile_change

        self.self_check_label: ui.label
        self.warning_chip: ui.chip
        self.change_label: ui.label
        self.profile_button: ui.button
        self.profile_menu: ui.menu
        self.topbar_right: ui.row
        self.tabs_el: ui.tabs

        self._build()

    def _build(self) -> None:
        with ui.header().classes(
            "w-full items-center justify-between px-4 py-2 bg-slate-900 text-white shadow"
        ):
            # Left section: App name, self-check status and warning chip
            with ui.row().classes("items-center gap-3"):
                ui.label("KrGenesis Mod").classes("text-lg font-bold tracking-tight text-white")

                check = self.state.index.self_check()
                self.self_check_label = ui.label(
                    f"{check.placed}/{check.total} values placed"
                ).classes("text-xs text-slate-400 font-mono")

                has_warning = (
                    bool(check.unplaced)
                    or bool(self.state.stale())
                    or bool(self.state.store.load_warnings)
                )
                self.warning_chip = ui.chip(
                    "Warning", icon="warning", color="amber-7"
                ).props("dense outline text-color=amber-4").classes("text-xs")
                self.warning_chip.visible = has_warning

            # Center section: Tab pills
            self.tabs_el = ui.tabs(
                value="Towers",
                on_change=lambda e: self.on_tab_change(e.value),
            ).props(
                "dense no-caps inline-label active-color=white active-bg-color=primary rounded indicator-color=transparent text-color=grey-5"
            ).classes("bg-slate-800/80 p-1 rounded-lg")
            with self.tabs_el:
                for tab in UI_TABS:
                    ui.tab(tab)

            # Right section: Change count, profile dropdown, and placeholder for Task 13
            self.topbar_right = ui.row().classes("items-center gap-3")
            with self.topbar_right:
                self.change_label = ui.label(self._change_text()).classes(
                    "text-xs text-slate-300 font-mono px-2 py-1 bg-slate-800 rounded"
                )

                self.profile_button = ui.button(
                    self.state.profile.name, icon="arrow_drop_down"
                ).props("flat dense no-caps text-color=white").mark("profile-menu")

                with self.profile_button:
                    self.profile_menu = ui.menu().classes("min-w-[180px]")
                    self._build_profile_menu()

        self._build_dialogs()

    def _change_text(self) -> str:
        count = self.state.change_count()
        return f"{count} change" if count == 1 else f"{count} changes"

    def _menu_item(self, text: str, on_click: Callable[[], None]) -> ui.menu_item:
        item = ui.menu_item(text, on_click=on_click)
        for child in item.default_slot.children:
            child.on("click", lambda _e, fn=on_click: fn())
        return item

    def _build_profile_menu(self) -> None:
        self.profile_menu.clear()
        with self.profile_menu:
            # List existing profiles
            for name in self.state.profile_names():
                is_active = name == self.state.profile.name
                item = self._menu_item(
                    name,
                    on_click=lambda n=name: self._switch_profile(n),
                )
                if is_active:
                    item.props("active")

            ui.separator()
            self._menu_item("New", on_click=self._open_new_dialog)
            self._menu_item("Duplicate", on_click=self._open_dup_dialog)
            self._menu_item("Rename", on_click=self._open_rename_dialog)
            self._menu_item("Delete", on_click=self._open_del_dialog)
    def _switch_profile(self, name: str) -> None:
        try:
            self.state.switch_profile(name)
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            ui.notify(str(exc), color="negative")

    def _build_dialogs(self) -> None:
        # New profile dialog
        with ui.dialog() as self.new_dialog, ui.card().classes("p-4 min-w-[340px]"):
            ui.label("New Profile").classes("text-lg font-bold mb-2")
            self.new_name_input = ui.input("Profile name").mark("profile-name").props("outlined dense autofocus")
            self.new_error_label = ui.label("").classes("text-xs text-red-500 font-medium mt-1")
            self.new_error_label.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self.new_dialog.close).props("flat dense")
                ui.button("Create", on_click=self._do_create_profile).props("unelevated dense color=primary")

        # Duplicate profile dialog
        with ui.dialog() as self.dup_dialog, ui.card().classes("p-4 min-w-[340px]"):
            ui.label("Duplicate Profile").classes("text-lg font-bold mb-2")
            self.dup_name_input = ui.input("New profile name").props("outlined dense autofocus")
            self.dup_error_label = ui.label("").classes("text-xs text-red-500 font-medium mt-1")
            self.dup_error_label.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self.dup_dialog.close).props("flat dense")
                ui.button("Duplicate", on_click=self._do_duplicate_profile).props("unelevated dense color=primary").mark("btn-duplicate")

        # Rename profile dialog
        with ui.dialog() as self.rename_dialog, ui.card().classes("p-4 min-w-[340px]"):
            ui.label("Rename Profile").classes("text-lg font-bold mb-2")
            self.rename_name_input = ui.input("New name").props("outlined dense autofocus")
            self.rename_error_label = ui.label("").classes("text-xs text-red-500 font-medium mt-1")
            self.rename_error_label.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self.rename_dialog.close).props("flat dense")
                ui.button("Rename", on_click=self._do_rename_profile).props("unelevated dense color=primary").mark("btn-rename")

        # Delete profile dialog
        with ui.dialog() as self.del_dialog, ui.card().classes("p-4 min-w-[340px]"):
            ui.label("Delete Profile").classes("text-lg font-bold mb-2")
            self.del_msg_label = ui.label("").classes("text-sm text-slate-700 mb-2")
            self.del_error_label = ui.label("").classes("text-xs text-red-500 font-medium mt-1")
            self.del_error_label.visible = False
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=self.del_dialog.close).props("flat dense")
                ui.button("Delete", on_click=self._do_delete_profile).props("unelevated dense color=negative").mark("btn-delete")

    def _open_new_dialog(self) -> None:
        self.new_name_input.value = ""
        self.new_error_label.text = ""
        self.new_error_label.visible = False
        self.new_dialog.open()

    def _do_create_profile(self) -> None:
        name = (self.new_name_input.value or "").strip()
        try:
            self.state.new_profile(name)
            self.new_dialog.close()
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            self.new_error_label.text = str(exc)
            self.new_error_label.visible = True

    def _open_dup_dialog(self) -> None:
        self.dup_name_input.set_value(f"{self.state.profile.name} (copy)")
        self.dup_error_label.text = ""
        self.dup_error_label.visible = False
        self.dup_dialog.open()

    def _do_duplicate_profile(self) -> None:
        name = (self.dup_name_input.value or "").strip()
        try:
            self.state.duplicate_profile(name)
            self.dup_dialog.close()
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            self.dup_error_label.text = str(exc)
            self.dup_error_label.visible = True

    def _open_rename_dialog(self) -> None:
        self.rename_name_input.set_value(self.state.profile.name)
        self.rename_error_label.text = ""
        self.rename_error_label.visible = False
        self.rename_dialog.open()

    def _do_rename_profile(self) -> None:
        name = (self.rename_name_input.value or "").strip()
        try:
            self.state.rename_profile(self.state.profile.name, name)
            self.rename_dialog.close()
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            self.rename_error_label.text = str(exc)
            self.rename_error_label.visible = True

    def _open_del_dialog(self) -> None:
        self.del_msg_label.text = f"Delete profile '{self.state.profile.name}'?"
        self.del_error_label.text = ""
        self.del_error_label.visible = False
        self.del_dialog.open()

    def _do_delete_profile(self) -> None:
        try:
            self.state.delete_profile(self.state.profile.name)
            self.del_dialog.close()
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            self.del_error_label.text = str(exc)
            self.del_error_label.visible = True

    def refresh(self) -> None:
        check = self.state.index.self_check()
        self.self_check_label.text = f"{check.placed}/{check.total} values placed"
        has_warning = (
            bool(check.unplaced)
            or bool(self.state.stale())
            or bool(self.state.store.load_warnings)
        )
        self.warning_chip.visible = has_warning
        self.change_label.text = self._change_text()
        self.profile_button.text = self.state.profile.name
        self._build_profile_menu()
