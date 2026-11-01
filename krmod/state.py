"""AppState controller: binds UI controls to gamedata, profiles and mod generation."""
from __future__ import annotations

import math
from typing import Sequence

from krmod.model.categories import CATEGORY_NAMES, category_of
from krmod.model.grouping import GroupIndex
from krmod.model.rows import StatRow, build_rows
from krmod.model.scaling import c2_range, common_pct, scale, warn
from krmod.model.values import BalanceTree, KeyPath, path_str
from krmod.modgen.launcher import RunOutcome, apply_and_run
from krmod.modgen.writer import ApplyResult, apply_mod, write_live
from krmod.paths import GamePaths
from krmod.profiles import (
    LiveSettings,
    Profile,
    ProfileError,
    ProfileStore,
    stale_changes,
    validate_speed_keys,
)


class AppState:
    def __init__(
        self,
        paths: GamePaths,
        tree: BalanceTree,
        index: GroupIndex,
        store: ProfileStore,
    ) -> None:
        self.paths = paths
        self.tree = tree
        self.index = index
        self.store = store
        self._rows_cache: dict[str, list[StatRow]] = {}

    @property
    def profile(self) -> Profile:
        return self.store.active()

    def current(self, path: KeyPath) -> float:
        if path in self.profile.changes:
            return float(self.profile.changes[path])
        return self.original(path)

    def original(self, path: KeyPath) -> float:
        return self.tree.original(path)

    def is_changed(self, path: KeyPath) -> bool:
        return path in self.profile.changes

    def change_count(self) -> int:
        return len(self.profile.changes)

    def card_has_changes(self, card_id: str) -> bool:
        return any(p in self.profile.changes for p in self.index.paths_of(card_id))

    def set_value(self, path: KeyPath, value: float) -> str | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Value must be a number, got {value!r}")
        if not math.isfinite(value):
            raise ValueError(f"Value must be finite, got {value!r}")
        if path not in self.tree.leaves:
            raise ValueError(f"Unknown path: {path}")
        leaf = self.tree.leaves[path]
        if leaf.kind != "num" or leaf.is_enum:
            raise ValueError(f"Path cannot be edited as numeric: {path}")

        orig = self.original(path)
        if float(value) == orig:
            if path in self.profile.changes:
                del self.profile.changes[path]
                self.store.save(self.profile)
            return None

        val = int(value) if leaf.is_whole and float(value).is_integer() else float(value)
        self.profile.changes[path] = val
        self.store.save(self.profile)
        return warn(path, float(value))

    def parse_and_set(self, path: KeyPath, text: str) -> tuple[bool, str | None]:
        if not isinstance(text, str):
            return False, "Not a number."
        s = text.strip()
        if not s:
            return False, "Value cannot be empty."
        try:
            val = float(s)
        except ValueError:
            return False, "Not a number."
        if not math.isfinite(val):
            return False, "Not a number."
        try:
            warning = self.set_value(path, val)
            return True, warning
        except ValueError as exc:
            return False, str(exc)

    def reset(self, path: KeyPath) -> None:
        if path in self.profile.changes:
            del self.profile.changes[path]
            self.store.save(self.profile)

    def reset_all(self) -> None:
        if self.profile.changes:
            self.profile.changes.clear()
            self.store.save(self.profile)

    def rows(self, card_id: str) -> list[StatRow]:
        if card_id not in self._rows_cache:
            card = self.index.card(card_id)
            paths = self.index.paths_of(card_id)
            self._rows_cache[card_id] = build_rows(card, paths, self.tree)
        return list(self._rows_cache[card_id])

    def _eligible_row_cells(self, row: StatRow) -> list[KeyPath]:
        cells: list[KeyPath] = []
        for p in row.cells:
            if p is None:
                continue
            leaf = self.tree.leaves.get(p)
            if leaf is None or leaf.kind != "num" or leaf.is_enum:
                continue
            if self.original(p) == 0:
                continue
            cells.append(p)
        return cells

    def scale_row(self, row: StatRow, pct: float) -> None:
        pct = round(pct, 1)
        cells = self._eligible_row_cells(row)
        for p in cells:
            orig = self.original(p)
            new_val = scale(orig, pct)
            if float(new_val) == orig:
                self.profile.changes.pop(p, None)
            else:
                leaf = self.tree.leaves[p]
                val = int(new_val) if leaf.is_whole and float(new_val).is_integer() else float(new_val)
                self.profile.changes[p] = val
        self.store.save(self.profile)

    def row_pct(self, row: StatRow) -> float | None:
        cells = self._eligible_row_cells(row)
        if not cells:
            return None
        pairs = [(self.original(p), self.current(p)) for p in cells]
        return common_pct(pairs)

    def _eligible_card_paths(
        self, card_id: str, category: str | None = None
    ) -> list[KeyPath]:
        paths: list[KeyPath] = []
        for p in self.index.paths_of(card_id):
            leaf = self.tree.leaves.get(p)
            if leaf is None or leaf.kind != "num" or leaf.is_enum:
                continue
            if self.original(p) == 0:
                continue
            cat = category_of(p)
            if cat is None:
                continue
            if category is not None and cat != category:
                continue
            paths.append(p)
        return paths

    def card_categories(self, card_id: str) -> list[str]:
        seen = {category_of(p) for p in self._eligible_card_paths(card_id)}
        return [c for c in CATEGORY_NAMES if c in seen]

    def scale_card(self, card_id: str, category: str, pct: float) -> None:
        pct = round(pct, 1)
        paths = self._eligible_card_paths(card_id, category)
        for p in paths:
            orig = self.original(p)
            new_val = scale(orig, pct)
            if float(new_val) == orig:
                self.profile.changes.pop(p, None)
            else:
                leaf = self.tree.leaves[p]
                val = int(new_val) if leaf.is_whole and float(new_val).is_integer() else float(new_val)
                self.profile.changes[p] = val
        self.store.save(self.profile)

    def card_pct(self, card_id: str, category: str) -> float | None:
        paths = self._eligible_card_paths(card_id, category)
        if not paths:
            return None
        pairs = [(self.original(p), self.current(p)) for p in paths]
        return common_pct(pairs)

    def set_level(
        self, path: KeyPath, value: float, locked_row: StatRow | None = None
    ) -> str | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Value must be a number, got {value!r}")
        if not math.isfinite(value):
            raise ValueError(f"Value must be finite, got {value!r}")
        if path not in self.tree.leaves:
            raise ValueError(f"Unknown path: {path}")
        leaf = self.tree.leaves[path]
        if leaf.kind != "num" or leaf.is_enum:
            raise ValueError(f"Path cannot be edited as numeric: {path}")

        orig = self.original(path)
        if locked_row is None or orig == 0:
            return self.set_value(path, value)

        ratio = float(value) / orig
        pct = round(ratio * 100.0, 1)

        cells = self._eligible_row_cells(locked_row)
        for p in cells:
            orig_j = self.original(p)
            new_val = scale(orig_j, pct)
            if float(new_val) == orig_j:
                self.profile.changes.pop(p, None)
            else:
                leaf_j = self.tree.leaves[p]
                val = int(new_val) if leaf_j.is_whole and float(new_val).is_integer() else float(new_val)
                self.profile.changes[p] = val
        self.store.save(self.profile)
        return warn(path, float(value))

    def c2_range(self, row: StatRow) -> tuple[float, float]:
        originals = [
            self.original(p)
            for p in row.cells
            if p is not None and p in self.tree.leaves
        ]
        return c2_range(originals)

    def set_live(
        self,
        speed: int | None = None,
        enemy_mult: float | None = None,
        troop_mult: float | None = None,
    ) -> None:
        new_speed = self.profile.live.speed if speed is None else speed
        new_enemy = self.profile.live.enemy_mult if enemy_mult is None else enemy_mult
        new_troop = self.profile.live.troop_mult if troop_mult is None else troop_mult
        test_live = LiveSettings(speed=new_speed, enemy_mult=new_enemy, troop_mult=new_troop)
        test_live.validate()
        self.profile.live = test_live
        self.store.save(self.profile)
        write_live(self.paths, self.profile.live)

    def set_unlock(self, on: bool) -> None:
        self.profile.unlock_tower_levels = bool(on)
        self.store.save(self.profile)

    def set_speed_keys(self, keys: Sequence[str]) -> None:
        valid_keys = validate_speed_keys(keys)
        self.profile.speed_keys = valid_keys
        self.store.save(self.profile)

    def stale(self) -> list[KeyPath]:
        return stale_changes(self.profile, self.tree)

    def alias_note(self, path: KeyPath) -> str | None:
        for src, dst in self.tree.aliases.items():
            if path == src:
                return f"linked with {path_str(dst)}"
            if path == dst:
                return f"linked with {path_str(src)}"
            if len(path) > len(src) and path[: len(src)] == src:
                target = dst + path[len(src) :]
                return f"linked with {path_str(target)}"
            if len(path) > len(dst) and path[: len(dst)] == dst:
                target = src + path[len(dst) :]
                return f"linked with {path_str(target)}"
        return None

    def profile_names(self) -> list[str]:
        return self.store.names()

    def switch_profile(self, name: str) -> None:
        self.store.switch(name)

    def new_profile(self, name: str) -> Profile:
        return self.store.create(name)

    def duplicate_profile(
        self, name_or_src: str, new_name: str | None = None
    ) -> Profile:
        if new_name is None:
            return self.store.duplicate(self.profile.name, name_or_src)
        return self.store.duplicate(name_or_src, new_name)

    def rename_profile(self, old: str, new: str) -> None:
        self.store.rename(old, new)

    def delete_profile(self, name: str) -> None:
        self.store.delete(name)

    def apply(self) -> ApplyResult:
        return apply_mod(self.paths, self.profile, self.tree)

    def apply_and_run(self) -> tuple[RunOutcome, ApplyResult]:
        return apply_and_run(self.paths, self.profile, self.tree)
