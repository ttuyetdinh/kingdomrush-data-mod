"""Placement rules for balance values, held as an ordered data table.

A rule is a path pattern plus card templates. Rules are tried in order and the
first match wins. Rule 1 (troop segments) and the catch-all rule 19 depend on
more than a pattern, so grouping.py handles them around this table.

Pattern tokens (one per path segment):
  "towers"          a literal segment
  "{t}"             any one segment, captured as t
  "{s:skill}"       a segment that is a skill segment (skill_*, ultimate, talent_*)
  "{p:power}"       a segment named power_<p>, captured as <p>
  "*"               one or more remaining segments (only valid as the last token)

Template strings use "{name}" for a capture, "{name|title}" for a captured
segment turned into plain English, and "{name|hero}" for the same with a
leading "hero_" dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tab = Literal["Towers", "Troops", "Heroes", "Skills", "Enemies", "Items", "Stages"]

TABS: tuple[Tab, ...] = (
    "Towers", "Troops", "Heroes", "Skills", "Enemies", "Items", "Stages",
)

TROOP_SEGMENTS = frozenset({"soldier", "special_soldier", "clone", "seedling"})

# Troop cards take their group from the root segment of the path.
TROOP_GROUP_BY_ROOT = {
    "towers": "Towers",
    "kr1_mode": "Classic towers",
    "powers": "Spells",
    "upgrades": "Spells",
    "heroes": "Heroes",
    "specials": "Stages",
    "enemies": "Enemies",
}
TROOP_GROUP_DEFAULT = "Other"

# Tab of the catch-all "other/<tab>" card, by root segment.
OTHER_TAB_BY_ROOT: dict[str, Tab] = {
    "towers": "Towers",
    "kr1_mode": "Towers",
    "heroes": "Heroes",
    "enemies": "Enemies",
    "items": "Items",
    "powers": "Skills",
    "upgrades": "Skills",
}
OTHER_TAB_DEFAULT: Tab = "Stages"

# Group display order inside a tab; unknown groups sort after these, by name.
GROUP_ORDER = (
    "Towers", "Classic towers", "Tower skills", "Classic tower skills",
    "Heroes", "Hero skills", "Spells", "Bosses",
)


def is_skill_segment(seg: str | int) -> bool:
    return isinstance(seg, str) and (
        seg.startswith("skill_") or seg == "ultimate" or seg.startswith("talent_")
    )


@dataclass(frozen=True)
class CardSpec:
    id: str
    tab: Tab
    title: str
    group: str
    prefix: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    number: int
    pattern: tuple[str, ...]
    home: CardSpec
    extra: tuple[CardSpec, ...] = ()


def _faction_spec(prefix: tuple[str, ...]) -> CardSpec:
    return CardSpec("enemies/{f}/{e}", "Enemies", "{e|title}", "{f|title}", prefix)


RULES: tuple[Rule, ...] = (
    # 2
    Rule(2, ("towers", "common", "*"),
         CardSpec("towers/common", "Towers", "Common", "Towers", ("towers", "common"))),
    # 3
    Rule(3, ("towers", "upgrades", "*"),
         CardSpec("towers/upgrades", "Towers", "Tower upgrades", "Towers",
                  ("towers", "upgrades"))),
    # 4
    Rule(4, ("towers", "{t}", "{s:skill}", "*"),
         CardSpec("towers/{t}", "Towers", "{t|title}", "Towers", ("towers", "{t}")),
         (CardSpec("skills/towers/{t}", "Skills", "{t|title}", "Tower skills",
                   ("towers", "{t}")),)),
    # 5
    Rule(5, ("towers", "{t}", "*"),
         CardSpec("towers/{t}", "Towers", "{t|title}", "Towers", ("towers", "{t}"))),
    # 6
    Rule(6, ("kr1_mode", "towers", "{t}", "{s:skill}", "*"),
         CardSpec("towers/kr1/{t}", "Towers", "Classic {t|title}", "Classic towers",
                  ("kr1_mode", "towers", "{t}")),
         (CardSpec("skills/towers/kr1/{t}", "Skills", "Classic {t|title}",
                   "Classic tower skills", ("kr1_mode", "towers", "{t}")),)),
    # 7
    Rule(7, ("kr1_mode", "towers", "{t}", "*"),
         CardSpec("towers/kr1/{t}", "Towers", "Classic {t|title}", "Classic towers",
                  ("kr1_mode", "towers", "{t}"))),
    # 8
    Rule(8, ("kr1_mode", "upgrades", "*"),
         CardSpec("skills/kr1_upgrades", "Skills", "Classic upgrades", "Classic towers",
                  ("kr1_mode", "upgrades"))),
    # 9
    Rule(9, ("heroes", "common", "*"),
         CardSpec("heroes/common", "Heroes", "Common", "Heroes", ("heroes", "common"))),
    # 10
    Rule(10, ("heroes", "{h}", "{s:skill}", "*"),
         CardSpec("heroes/{h}", "Heroes", "{h|hero}", "Heroes", ("heroes", "{h}")),
         (CardSpec("skills/heroes/{h}", "Skills", "{h|hero}", "Hero skills",
                   ("heroes", "{h}")),)),
    # 11
    Rule(11, ("heroes", "{h}", "*"),
         CardSpec("heroes/{h}", "Heroes", "{h|hero}", "Heroes", ("heroes", "{h}"))),
    # 12
    Rule(12, ("powers", "{p}", "*"),
         CardSpec("skills/powers/{p}", "Skills", "{p|title}", "Spells", ("powers", "{p}"))),
    # 13
    Rule(13, ("upgrades", "{p:power}", "*"),
         CardSpec("skills/powers/{p}", "Skills", "{p|title}", "Spells", ("powers", "{p}"))),
    # 14
    Rule(14, ("enemies", "jt_boss", "*"),
         CardSpec("enemies/jt_boss", "Enemies", "JT boss", "Bosses",
                  ("enemies", "jt_boss"))),
    Rule(14, ("enemies", "lord_blackburn_boss", "*"),
         CardSpec("enemies/lord_blackburn_boss", "Enemies", "Lord Blackburn boss", "Bosses",
                  ("enemies", "lord_blackburn_boss"))),
    # 15
    Rule(15, ("enemies", "{f}", "{e}", "*"), _faction_spec(("enemies", "{f}", "{e}"))),
    # 16
    Rule(16, ("items", "{i}", "*"),
         CardSpec("items/{i}", "Items", "{i|title}", "Items", ("items", "{i}"))),
    # 17
    Rule(17, ("specials", "towers", "{name}", "*"),
         CardSpec("stages/towers/{name}", "Stages", "{name|title}", "Stage towers",
                  ("specials", "towers", "{name}"))),
    Rule(17, ("specials", "heroes", "{name}", "*"),
         CardSpec("stages/heroes/{name}", "Stages", "{name|hero}", "Stage heroes",
                  ("specials", "heroes", "{name}"))),
    # 18
    Rule(18, ("specials", "{s}", "*"),
         CardSpec("stages/{s}", "Stages", "{s|title}", "Stages", ("specials", "{s}"))),
)
