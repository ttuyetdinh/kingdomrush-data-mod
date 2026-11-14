"""Placement of every balance value into exactly one tab and card.

place() applies the ordered rules of grouping_rules.py. GroupIndex runs it over a
whole BalanceTree and answers the queries the UI needs. Placement depends only on
a path's parent table (the last segment is never part of a pattern), so it is
computed once per table and shared by that table's leaves.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .grouping_rules import (
    GROUP_ORDER,
    OTHER_TAB_BY_ROOT,
    OTHER_TAB_DEFAULT,
    RULES,
    TABS,
    TROOP_GROUP_BY_ROOT,
    TROOP_GROUP_DEFAULT,
    TROOP_SEGMENTS,
    CardSpec,
    Tab,
)
from .values import BalanceTree, KeyPath, path_str

_FIELD = re.compile(r"\{(\w+)(?:\|(\w+))?\}")


@dataclass(frozen=True)
class Card:
    """One tile in a tab. A summary card spans many units: it offers Quick scale over all its
    values but no level table, and it is never the home of a value (see card_of)."""

    id: str
    tab: Tab
    title: str
    group: str
    prefix: KeyPath
    summary: bool = False


# Summary card over every enemy and boss value (Enemies tab), listed before the factions.
ALL_ENEMIES = Card(
    id="enemies/all", tab="Enemies", title="All enemies", group="All enemies",
    prefix=("enemies",), summary=True,
)


@dataclass(frozen=True)
class SelfCheck:
    total: int
    placed: int
    unplaced: list[KeyPath]
    other: list[KeyPath]


def humanize(seg: str | int) -> str:
    """Plain-English form of a key: underscores to spaces, first letter upper."""
    text = str(seg).replace("_", " ")
    return text[:1].upper() + text[1:]


def _hero_name(seg: str | int) -> str:
    text = str(seg)
    return humanize(text[len("hero_"):] if text.startswith("hero_") else text)


_FILTERS = {"title": humanize, "hero": _hero_name}


def _fill(template: str, caps: dict[str, str]) -> str:
    def sub(m: re.Match[str]) -> str:
        value = caps[m.group(1)]
        flt = m.group(2)
        return _FILTERS[flt](value) if flt else value

    return _FIELD.sub(sub, template)


def _match(pattern: tuple[str, ...], path: tuple[str | int, ...]) -> dict[str, str] | None:
    if len(path) < len(pattern):
        return None
    caps: dict[str, str] = {}
    for i, tok in enumerate(pattern):
        if tok == "*":
            return caps  # last token: swallows the rest, which is non-empty
        seg = path[i]
        if tok.startswith("{"):
            name, _, kind = tok[1:-1].partition(":")
            if kind == "power":
                if not (isinstance(seg, str) and seg.startswith("power_")
                        and len(seg) > len("power_")):
                    return None
                seg = seg[len("power_"):]
            caps[name] = str(seg)
        elif seg != tok:
            return None
    return caps if len(path) == len(pattern) else None


def _build(spec: CardSpec, caps: dict[str, str]) -> Card:
    return Card(
        id=_fill(spec.id, caps),
        tab=spec.tab,
        title=_fill(spec.title, caps),
        group=_fill(spec.group, caps),
        prefix=tuple(_fill(seg, caps) for seg in spec.prefix),
    )


def _troop_card(prefix: KeyPath) -> Card:
    root = str(prefix[0])
    owner = [str(s) for s in prefix[1:-1]]
    if root in ("specials", "kr1_mode") and owner and owner[0] in ("towers", "heroes"):
        owner = owner[1:]
    words = []
    for seg in owner + [str(prefix[-1])]:
        for strip in ("hero_", "power_"):
            if seg.startswith(strip) and len(seg) > len(strip):
                seg = seg[len(strip):]
        words.append(seg.replace("_", " "))
    title = humanize(" ".join(words))
    if root == "kr1_mode":
        title = "Classic " + title
    return Card(
        id="troops/" + path_str(prefix),
        tab="Troops",
        title=title,
        group=TROOP_GROUP_BY_ROOT.get(root, TROOP_GROUP_DEFAULT),
        prefix=prefix,
    )


def _other_card(root: str) -> Card:
    tab = OTHER_TAB_BY_ROOT.get(root, OTHER_TAB_DEFAULT)
    return Card(id=f"other/{tab}", tab=tab, title="Other", group="Other", prefix=())


@lru_cache(maxsize=None)
def _place_parent(parent: KeyPath) -> Card:
    # Rule 1: a troop segment anywhere from index 2 on, inside the parent table.
    for i in range(2, len(parent)):
        if parent[i] in TROOP_SEGMENTS:
            return _troop_card(parent[: i + 1])
    path = parent + (None,)  # the leaf's own name never takes part in matching
    for rule in RULES:
        caps = _match(rule.pattern, path)  # type: ignore[arg-type]
        if caps is not None:
            return _build(rule.card, caps)
    root = parent[0] if parent and isinstance(parent[0], str) else ""
    return _other_card(root)


def place(path: KeyPath) -> Card:
    """The one card that shows the value at path."""
    return _place_parent(tuple(path[:-1]))


def _seg_key(seg: str | int) -> tuple[int, int, str]:
    return (0, seg, "") if isinstance(seg, int) else (1, 0, seg)


def _path_key(p: KeyPath) -> tuple:
    return tuple(_seg_key(s) for s in p)


def _card_order(card: Card) -> tuple:
    try:
        rank = GROUP_ORDER.index(card.group)
    except ValueError:
        rank = len(GROUP_ORDER)
    return (rank, card.group, card.title, card.id)


class GroupIndex:
    def __init__(self) -> None:
        self._cards: dict[str, Card] = {}
        self._paths: dict[str, list[KeyPath]] = {}
        self._placements: dict[KeyPath, Card] = {}
        self._numeric: list[KeyPath] = []
        self._by_tab: dict[str, list[Card]] = {tab: [] for tab in TABS}

    @classmethod
    def build(cls, tree: BalanceTree) -> "GroupIndex":
        idx = cls()
        for p, leaf in tree.leaves.items():
            card = place(p)
            idx._placements[p] = card
            if leaf.kind == "num":
                idx._numeric.append(p)
            idx._cards.setdefault(card.id, card)
            idx._paths.setdefault(card.id, []).append(p)
        idx._cards[ALL_ENEMIES.id] = ALL_ENEMIES
        idx._paths[ALL_ENEMIES.id] = [p for p in tree.leaves if p[0] == ALL_ENEMIES.prefix[0]]
        for paths in idx._paths.values():
            paths.sort(key=_path_key)
        for card in idx._cards.values():
            idx._by_tab[card.tab].append(card)
        for cards in idx._by_tab.values():
            cards.sort(key=_card_order)
        return idx

    def cards(self, tab: Tab) -> list[Card]:
        return list(self._by_tab[tab])

    def card(self, card_id: str) -> Card:
        return self._cards[card_id]

    def paths_of(self, card_id: str) -> list[KeyPath]:
        return list(self._paths[card_id])

    def card_of(self, path: KeyPath) -> Card:
        return self._placements[path]

    def self_check(self) -> SelfCheck:
        unplaced: list[KeyPath] = []
        other: list[KeyPath] = []
        placed = 0
        for p in self._numeric:
            card = self._placements.get(p)
            if card is None or card.id not in self._paths:
                unplaced.append(p)
                continue
            placed += 1
            if card.id.startswith("other/"):
                other.append(p)
        return SelfCheck(len(self._numeric), placed, unplaced, other)
