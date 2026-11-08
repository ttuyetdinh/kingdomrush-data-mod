"""Top bar component: app title, tabs, self-check, profile selector and change count."""
from __future__ import annotations

from typing import Awaitable, Callable

from nicegui import ui

UI_TABS: tuple[str, ...] = (
    "Towers", "Troops", "Heroes", "Skills", "Enemies", "Items", "Stages", "Rules"
)
from krmod.profiles import ProfileError, slug
from krmod.state import AppState
from krmod.ui import gamefolder
from krmod.ui.livebox import LiveBox


class TopBar:
    def __init__(
        self,
        state: AppState,
        on_tab_change: Callable[[str], None],
        on_profile_change: Callable[[], None],
        on_game_dir: Callable[[str], Awaitable[bool]],
        on_refresh: Callable[[], None],
    ) -> None:
        self.state = state
        self.on_tab_change = on_tab_change
        self.on_profile_change = on_profile_change
        self.on_game_dir = on_game_dir
        self.on_refresh = on_refresh

        self.self_check_label: ui.label
        self.warning_chip: ui.chip
        self.warning_tip: ui.tooltip
        self.change_label: ui.label
        self.profile_button: ui.button
        self.profile_menu: ui.menu
        self.topbar_right: ui.row
        self.tabs_el: ui.tabs
        self.speed_buttons: dict[int, ui.button] = {}
        self.enemy_box: LiveBox
        self.troop_box: LiveBox
        self._build()

    def _build(self) -> None:
        # One row from 1280 px (Tailwind xl); below that two rows: row 1 is the title block and
        # the tabs, row 2 the live controls and the right end. `xl:contents` dissolves row 1 so
        # its children join the header row on wide windows.
        with ui.header().classes(
            "w-full flex flex-col xl:flex-row flex-nowrap items-stretch xl:items-center justify-between gap-1 xl:gap-0 "
            "px-3 py-2 bg-slate-900 text-white shadow"
        ):
            with ui.row().classes("items-center justify-between gap-x-3 flex-nowrap min-w-0 xl:contents"):
                # Title block: app name, with the self-check status and warning chip under it
                with ui.column().classes("gap-0 min-w-0 shrink"):
                    ui.label("KrGenesis Mod").classes("text-lg font-bold tracking-tight text-white leading-tight")
                    with ui.row().classes("items-center gap-2 flex-nowrap min-w-0 w-full"):
                        check = self.state.index.self_check()
                        self.self_check_label = ui.label(
                            f"{check.placed}/{check.total} values placed"
                        ).classes("text-xs text-slate-400 font-mono leading-tight shrink-0 whitespace-nowrap")

                        has_warning, warn_text = self._warning_summary()
                        # A long warning is cut short in the chip; the tooltip keeps the full text.
                        self.warning_chip = ui.chip(
                            warn_text, icon="warning", color="amber-7"
                        ).props("dense outline text-color=amber-4").classes(
                            "text-xs m-0 min-w-0 shrink overflow-hidden [&>div]:block [&>div]:truncate"
                        ).mark("warning-chip")
                        self.warning_chip.visible = has_warning
                        with self.warning_chip:
                            self.warning_tip = ui.tooltip(warn_text)

                # Tab pills
                self.tabs_el = ui.tabs(
                    value="Towers",
                    on_change=lambda e: self.on_tab_change(e.value),
                ).props(
                    "dense no-caps inline-label active-color=white active-bg-color=primary rounded indicator-color=transparent text-color=grey-5"
                ).classes("bg-slate-800/80 p-0.5 rounded-lg shrink-0")
                with self.tabs_el:
                    for tab in UI_TABS:
                        ui.tab(tab).props("dense").classes("px-1.5 py-0 min-h-0 text-xs")

            # Live controls, change count, game folder, profile dropdown
            self.topbar_right = ui.row().classes(
                "items-center gap-1.5 flex-nowrap shrink-0 xl:pr-4"
            )
            with self.topbar_right:
                # Speed buttons
                with ui.row().classes("items-center bg-slate-800 rounded p-0.5 gap-0.5 shrink-0"):
                    for s in (1, 2, 3):
                        btn = (
                            ui.button(
                                f"×{s}",
                                on_click=lambda sp=s: self._set_speed(sp),
                            )
                            .props("dense no-caps")
                            .mark(f"speed-{s}")
                        )
                        self.speed_buttons[s] = btn
                self._update_speed_buttons()

                # Live enemy multiplier and troop count boxes
                self.enemy_box = LiveBox(self.state, "enemy_mult", "enemy-mult", self.on_refresh, dark=True)
                self.troop_box = LiveBox(self.state, "troop_delta", "troop-delta", self.on_refresh, dark=True)

                # Right end: pushed to the right of row 2
                with ui.row().classes("items-center gap-1.5 flex-nowrap shrink-0 ml-auto"):
                    self.change_label = ui.label(self._change_text()).classes(
                        "text-xs text-slate-300 font-mono px-2 py-1 bg-slate-800 rounded whitespace-nowrap"
                    )

                    ui.button(icon="folder_open", on_click=self._open_game_dialog).props(
                        "flat dense round text-color=white"
                    ).mark("game-folder").tooltip(f"Game folder: {self.state.paths.game_dir}")

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

    def _warning_summary(self) -> tuple[bool, str]:
        check = self.state.index.self_check()
        parts: list[str] = []
        if self.state.store.load_warnings:
            files = [w.split(":")[0].strip() for w in self.state.store.load_warnings]
            parts.append(f"load warnings: {', '.join(files)}")
        if check.unplaced:
            parts.append(f"{len(check.unplaced)} unplaced")
        stale_count = len(self.state.stale())
        if stale_count:
            parts.append(f"{stale_count} stale")

        if not parts:
            return False, ""
        return True, f"Warning ({'; '.join(parts)})"

    def _build_profile_menu(self) -> None:
        self.profile_menu.clear()
        with self.profile_menu:
            # List existing profiles
            for name in self.state.profile_names():
                is_active = name == self.state.profile.name
                item = ui.menu_item(
                    name,
                    on_click=lambda n=name: self._switch_profile(n),
                ).mark(f"profile-item-{slug(name)}")
                if is_active:
                    item.props("active")

            ui.separator()
            ui.menu_item("New", on_click=self._open_new_dialog).mark("profile-new New")
            ui.menu_item("Duplicate", on_click=self._open_dup_dialog).mark("profile-duplicate Duplicate")
            ui.menu_item("Rename", on_click=self._open_rename_dialog).mark("profile-rename Rename")
            ui.menu_item("Delete", on_click=self._open_del_dialog).mark("profile-delete Delete")

    def _switch_profile(self, name: str) -> None:
        try:
            self.state.switch_profile(name)
            self.profile_menu.close()
            self.refresh()
            self.on_profile_change()
        except ProfileError as exc:
            ui.notify(str(exc), color="negative")

    def _build_dialogs(self) -> None:
        # Game folder dialog
        with ui.dialog().mark("game-dialog") as self.game_dialog, ui.card().classes("p-4 min-w-[440px] gap-2"):
            ui.label("Game folder").classes("text-lg font-bold")
            ui.label(str(self.state.paths.game_dir)).classes(
                "text-xs text-slate-600 font-mono break-all"
            ).mark("game-dir-current")
            note = gamefolder.env_override_note()
            if note:
                ui.label(note).classes("text-xs text-amber-700")
            ui.label("Choose another folder with Kingdom Rush Genesis.exe. Your profiles and changes stay.").classes(
                "text-xs text-slate-500"
            )
            gamefolder.render_chooser(str(self.state.paths.game_dir), self._do_game_dir)
            with ui.row().classes("w-full justify-end"):
                ui.button("Close", on_click=self.game_dialog.close).props("flat dense")

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

    def _open_game_dialog(self) -> None:
        self.game_dialog.open()

    async def _do_game_dir(self, text: str) -> bool:
        ok = await self.on_game_dir(text)
        if ok:
            self.game_dialog.close()
        return ok

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
        has_warning, warn_text = self._warning_summary()
        self.warning_chip.text = warn_text
        self.warning_tip.text = warn_text
        self.warning_chip.visible = has_warning
        self.change_label.text = self._change_text()
        self.profile_button.text = self.state.profile.name
        self._build_profile_menu()
        self._update_speed_buttons()
        self.enemy_box.refresh()
        self.troop_box.refresh()

    def _update_speed_buttons(self) -> None:
        curr_speed = self.state.profile.live.speed
        for s, btn in self.speed_buttons.items():
            if s == curr_speed:
                btn.props(
                    remove="flat text-color=slate-400",
                    add="unelevated color=primary text-color=white",
                )
            else:
                btn.props(
                    remove="unelevated color=primary text-color=white",
                    add="flat text-color=slate-400",
                )

    def _set_speed(self, speed: int) -> None:
        try:
            self.state.set_live(speed=speed)
            self._update_speed_buttons()
            self.on_refresh()
        except ProfileError as exc:
            ui.notify(str(exc), color="negative")
