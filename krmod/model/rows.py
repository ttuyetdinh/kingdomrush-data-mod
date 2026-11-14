"""Stat rows: the editable lines of one card.

Per-level arrays (price.1, price.2, ...) collapse into one row with one cell per
level; every other leaf is a one-cell row.
"""
from __future__ import annotations

from dataclasses import dataclass

from .grouping import Card
from .grouping_rules import is_skill_segment
from .values import BalanceTree, KeyPath, is_enum_key

HERO_BARS_LABEL = "Hero screen bars"


@dataclass(frozen=True)
class StatRow:
    id: str
    group: str
    label: str
    cells: tuple[KeyPath | None, ...]
    is_enum: bool
    read_only: bool
    is_skill: bool = False


def friendly_label(key: str) -> str:
    words = str(key).split("_")
    is_info = len(words) > 1 and words[0] == "s"
    if is_info:
        words = words[1:]
    suffix = ""
    if len(words) > 1 and words[-1] in ("max", "min"):
        suffix = f" ({words[-1]})"
        words = words[:-1]
    if is_info:
        suffix = f"{suffix} (info text)"
    words = ["HP" if w == "hp" else w for w in words]
    text = " ".join(words)
    return text[:1].upper() + text[1:] + suffix


def _relative(card: Card, path: KeyPath) -> KeyPath:
    """The path below the card, with a foreign path (upgrades.power_<p>) kept apart."""
    n = len(card.prefix)
    if path[:n] == card.prefix:
        return tuple(path[n:])
    if path[0] == "upgrades" and len(path) > 2:
        return ("upgrades",) + tuple(path[2:])
    return tuple(path)


def _group_label(card: Card, group: str) -> str:
    if group == "stats" and len(card.prefix) == 2 and card.prefix[0] == "heroes":
        return HERO_BARS_LABEL
    return group


def _is_skill_group(card: Card, rel: KeyPath) -> bool:
    """Rows of a tower's or hero's skills (skill_*, ultimate, talent_*, hero upgrades)."""
    if card.tab not in ("Towers", "Heroes") or len(rel) < 2:
        return False
    return is_skill_segment(rel[0]) or (card.tab == "Heroes" and rel[0] == "upgrades")


def build_rows(card: Card, paths: list[KeyPath], tree: BalanceTree) -> list[StatRow]:
    leaves = tree.leaves
    # Parent tables holding an integer-keyed numeric leaf: candidates for level rows.
    candidates = {
        p[:-1] for p in paths
        if isinstance(p[-1], int) and leaves[p].kind == "num"
    }
    children: dict[KeyPath, set[str | int]] = {c: set() for c in candidates}
    if candidates:
        for p in paths:
            for depth in range(1, len(p)):
                parent = p[:depth]
                if parent in children:
                    children[parent].add(p[depth])
    arrays: set[KeyPath] = set()
    for parent, keys in children.items():
        if all(isinstance(k, int) for k in keys) and keys == set(range(1, len(keys) + 1)):
            if all(leaves[parent + (k,)].kind == "num" for k in keys):
                arrays.add(parent)

    rows: dict[KeyPath, tuple[str, str, str, list[KeyPath | None], bool, bool, bool]] = {}
    for p in paths:
        leaf = leaves[p]
        parent = p[:-1]
        if parent in arrays:
            owner: KeyPath = parent
            key = parent[-1]
            slot = int(p[-1]) - 1
        else:
            owner = p
            key = p[-1]
            slot = 0
        rel = _relative(card, owner)
        group = ".".join(str(s) for s in rel[:-1])
        entry = rows.get(owner)
        if entry is None:
            if isinstance(key, int):
                label = f"{friendly_label(str(owner[-2]))} {key}" if len(owner) > 1 else str(key)
            else:
                label = friendly_label(key)
            enum = leaf.kind == "num" and is_enum_key(key)
            entry = (
                ".".join(str(s) for s in rel),
                _group_label(card, group),
                label,
                [],
                enum,
                enum or leaf.kind != "num",
                _is_skill_group(card, rel),
            )
            rows[owner] = entry
        cells = entry[3]
        while len(cells) <= slot:
            cells.append(None)
        cells[slot] = p

    out = [
        StatRow(rid, group, label, tuple(cells), enum, ro, skill)
        for rid, group, label, cells, enum, ro, skill in rows.values()
    ]
    # The unit's own stats first, then its skill sections, each block sorted by group.
    out.sort(key=lambda r: (r.is_skill, r.group != "", r.group, r.id))
    return out
