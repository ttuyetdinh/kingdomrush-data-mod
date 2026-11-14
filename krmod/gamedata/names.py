"""Card and skill section names as the game shows them, read from the game's English text.

The text table is _assets/kr6-desktop/strings/en.lua inside the exe zip. The keys below link
each card (and each skill section) to the game's own text key; they were read from the
i18n_key of the game's unit templates. A card or section without a key, or whose key the text
table lacks, keeps the app's own title.
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from krmod.gamedata.luart import LuaRuntime
from krmod.paths import GamePaths

STRINGS_FILE = "_assets/kr6-desktop/strings/en.lua"

_WALKER = r"""
local strings = assert(loadstring(KRMOD_STRINGS_BLOB))()
local out = {}
for k, v in pairs(strings) do
  if type(k) == "string" and type(v) == "string" then
    out[#out + 1] = k .. "\t" .. v:gsub("[\t\n]", " ")
  end
end
return table.concat(out, "\n")
"""

# Text keys (without _NAME / _TITLE) of tower types. Most follow TOWER_<BALANCE KEY>; a key that
# ends in a level number names the level 1 tower (its " I" is dropped).
_TOWER_KEYS = {"light_priestess": "TOWER_PRIESTESS_1", "sunray_master": "TOWER_SUNRAY_1"}
_KR1_TOWER_KEYS = {
    "arcane": "TOWER_ARCANE", "archers": "TOWER_ARCHER_1", "barbarians": "TOWER_BARBARIANS",
    "barracks": "TOWER_BARRACK_1", "bfg": "TOWER_BFG", "engineers": "TOWER_ENGINEER_1",
    "mages": "TOWER_MAGE_1", "musketeers": "TOWER_MUSKETEERS", "paladins": "TOWER_PALADINS",
    "ranger": "TOWER_RANGERS", "sorcerer": "TOWER_SORCERER", "tesla": "TOWER_TESLA",
}
# Classic tower skill tables -> text key.
_KR1_SKILL_KEYS = {
    "arcane": {"disintegrate": "TOWER_ARCANE_DESINTEGRATE", "teleport": "TOWER_ARCANE_TELEPORT"},
    "barbarians": {"dual": "TOWER_BARBARIANS_DOUBLE_AXE", "throwing": "TOWER_BARBARIANS_THROWING_AXES",
                   "twister": "TOWER_BARBARIANS_TWISTER"},
    "bfg": {"cluster": "TOWER_BFG_CLUSTER", "missile": "TOWER_BFG_MISSILE"},
    "musketeers": {"shrapnel": "TOWER_MUSKETEERS_SHRAPNEL", "sniper": "TOWER_MUSKETEERS_SNIPER"},
    "paladins": {"healing": "TOWER_PALADINS_HEALING", "holystrike": "TOWER_PALADINS_HOLY_STRIKE",
                 "shield": "TOWER_PALADINS_SHIELD"},
    "ranger": {"poison": "TOWER_RANGERS_POISON", "thorn": "TOWER_RANGERS_THORNS"},
    "sorcerer": {"elemental": "TOWER_SORCERER_ELEMENTAL", "polymorph": "TOWER_SORCERER_POLIMORPH"},
    "tesla": {"bolt": "TOWER_TESLA_CHARGED_BOLT", "overcharge": "TOWER_TESLA_OVERCHARGE"},
}
# Cards whose key does not follow their family's pattern.
_CARD_KEYS = {
    "enemies/jt_boss": "ENEMY_BOSS_STAGE_10",
    "enemies/lord_blackburn_boss": "ENEMY_BOSS_STAGE_15",
    "enemies/orcs/boss": "ENEMY_BOSS_STAGE_08",
    "enemies/spiders/boss_spider": "ENEMY_BOSS_STAGE_11",
    "enemies/deep_trolls/troll_boss": "ENEMY_BOSS_STAGE_13",
    "stages/heroes/hero_alleria": "HERO_STAGE_05_ALLERIA",
    "stages/heroes/hero_denas": "HERO_STAGE_18_DENAS",
    "stages/towers/stage_11_tower_camp": "TOWER_STAGE_11_CAMP_LVL1",
}
# Troops: card id -> (text key of the unit, or None to use the owner card's name, owner card
# id, suffix). Units the game only names at random use their owner's name; a troop missing
# here keeps the app's title.
_TROOPS: dict[str, tuple[str | None, str, str]] = {
    "troops/towers.alchemist.skill_b.soldier": ("TOWER_ALCHEMIST_4_SKILL_B_UNIT", "", ""),
    "troops/towers.crossbows.ultimate.soldier": ("TOWER_CROSSBOWS_4_ULTIMATE_UNIT", "", ""),
    "troops/towers.knights.soldier": (None, "towers/knights", " soldier"),
    "troops/towers.miners.skill_a.soldier": ("TOWER_MINERS_4_SKILL_A", "", ""),
    "troops/towers.miners.soldier": (None, "towers/miners", " soldier"),
    "troops/towers.sunray_master.skill_a.soldier": ("TOWER_SUNRAY_MASTER_EARTH_ELEMENTAL", "", ""),
    "troops/towers.tree.soldier": (None, "towers/tree", " soldier"),
    "troops/towers.tree.ultimate.seedling": ("TOWER_TREE_4_ULT", "", ""),
    "troops/towers.wildcat.soldier": (None, "towers/wildcat", " soldier"),
    "troops/kr1_mode.towers.barbarians.soldier": (None, "towers/kr1/barbarians", " soldier"),
    "troops/kr1_mode.towers.barracks.soldier": (None, "towers/kr1/barracks", " soldier"),
    "troops/kr1_mode.towers.paladins.soldier": (None, "towers/kr1/paladins", " soldier"),
    "troops/kr1_mode.towers.sorcerer.elemental.soldier": ("SOLDIER_ELEMENTAL", "", ""),
    "troops/heroes.hero_drakkan.skill_c.clone": ("HERO_DRAKKAN_CLONE", "", ""),
    "troops/heroes.hero_myriath.clone": ("HERO_MYRIATH_CLONE", "", ""),
    "troops/powers.aspect_of_sol.soldier": (None, "spells/aspect_of_sol", " soldier"),
    "troops/powers.musketeers.soldier": (None, "spells/musketeers", " soldier"),
    "troops/powers.reinforcements.soldier": (None, "spells/reinforcements", " soldier"),
    "troops/powers.reinforcements.special_soldier": (None, "spells/reinforcements", " special soldier"),
    "troops/specials.heroes.hero_alleria.wildcat.soldier": ("SOLDIER_ALLERIA_CAT", "", ""),
    "troops/specials.heroes.hero_denas.denas_guards.soldier": (None, "stages/heroes/hero_denas", " guard"),
    "troops/specials.towers.stage_07_barn.soldier": (None, "stages/towers/stage_07_barn", " soldier"),
    "troops/specials.towers.stage_11_tower_camp.soldier": (None, "stages/towers/stage_11_tower_camp", " soldier"),
    "troops/specials.towers.stage_14_armory.soldier": (None, "stages/towers/stage_14_armory", " soldier"),
}

_SMALL_WORDS = frozenset({"a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to"})
_ROMAN = frozenset({"I", "II", "III", "IV", "V"})


def _cap(word: str) -> str:
    low = word.lower()
    return low[:1].upper() + low[1:]


def tidy(text: str) -> str:
    """Game text as a title: ALL CAPS becomes Title Case (small words lower, each part of a
    hyphenated word capitalized, words with digits, dots or roman numerals kept); text that
    already has lower case is kept."""
    if any(ch.islower() for ch in text):
        return text
    out = []
    for i, w in enumerate(text.split(" ")):
        if any(ch.isdigit() or ch == "." for ch in w) or w in _ROMAN:
            out.append(w)
        elif i > 0 and w.lower() in _SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append("-".join(_cap(part) for part in w.split("-")))
    return " ".join(out)


@dataclass
class GameNames:
    """Lookups over the game's text table (key -> text)."""

    strings: Mapping[str, str] = field(default_factory=dict)

    def text(self, key: str | None) -> str | None:
        """Tidy text of key + _NAME or _TITLE; a level 1 key ("..._1", "..._LVL1") drops its " I"."""
        if not key:
            return None
        raw = self.strings.get(key + "_NAME") or self.strings.get(key + "_TITLE")
        if raw is None:
            return None
        name = tidy(raw.strip())
        if key.endswith("1") and name.endswith(" I"):
            name = name[:-2]
        return name

    def card_key(self, card_id: str) -> str | None:
        if card_id in _CARD_KEYS:
            return _CARD_KEYS[card_id]
        parts = card_id.split("/")
        family = parts[0]
        if family == "towers" and len(parts) == 3 and parts[1] == "kr1":
            return _KR1_TOWER_KEYS.get(parts[2])
        if family == "towers" and len(parts) == 2:
            return _TOWER_KEYS.get(parts[1], "TOWER_" + parts[1].upper())
        if family == "heroes" and parts[1].startswith("hero_"):
            return parts[1].upper()
        if family == "spells":
            return "POWER_" + parts[1].upper()
        if family == "items":
            return "ITEM_" + parts[1].upper()
        if family == "enemies" and len(parts) == 3:
            return "ENEMY_" + parts[2].upper()
        if family == "stages" and len(parts) == 3 and parts[1] == "towers":
            return "TOWER_" + parts[2].upper()
        if family == "stages" and len(parts) == 2 and re.fullmatch(r"stage_\d+", parts[1]):
            return f"LEVEL_{int(parts[1][len('stage_'):])}"
        return None

    def card_name(self, card_id: str) -> str | None:
        if card_id in _TROOPS:
            key, owner, suffix = _TROOPS[card_id]
            base = self.text(key) if key else self.card_name(owner)
            return base + suffix if base else None
        return self.text(self.card_key(card_id))

    def section_name(self, card_id: str, group: str) -> str | None:
        """Game name of a skill section (skill_a, ultimate, talent_1, a spell upgrade, a
        classic tower skill), or None."""
        parts = card_id.split("/")
        seg = group.split(".")
        if parts[0] == "towers" and len(parts) == 2 and len(seg) == 1:
            base = self.card_key(card_id)
            if base is None:
                return None
            base = re.sub(r"_\d+$", "", base)
            if re.fullmatch(r"skill_[a-c]", group):
                return self.text(f"{base}_4_SKILL_{group[-1].upper()}")
            if group == "ultimate":
                return self.text(f"{base}_4_ULT")
        if parts[0] == "towers" and len(parts) == 3 and parts[1] == "kr1" and len(seg) == 1:
            return self.text(_KR1_SKILL_KEYS.get(parts[2], {}).get(group))
        if parts[0] == "heroes" and parts[1].startswith("hero_") and len(seg) == 1:
            hero = parts[1].upper()
            if re.fullmatch(r"skill_[a-c]", group):
                return self.text(f"{hero}_SKILL_{group[-1].upper()}_1")
            if re.fullmatch(r"talent_\d", group):
                return self.text(f"{hero}_TALENT_{group[-1]}")
            if group == "ultimate":
                return self.text(f"{hero}_ULT")
        if parts[0] == "spells" and len(seg) == 2 and seg[0] == "upgrades":
            return self.text(f"POWER_{parts[1].upper()}_{seg[1].upper()}")
        return None

    def names_for(self, card_ids: Iterable[str]) -> dict[str, str]:
        out = {}
        for cid in card_ids:
            name = self.card_name(cid)
            if name:
                out[cid] = name
        return out


def read_game_names(paths: GamePaths) -> GameNames:
    """The game's English text table; empty (every card keeps its own title) when unreadable."""
    try:
        with zipfile.ZipFile(paths.exe) as exe, LuaRuntime(paths.lua_dll) as lua:
            lua.set_global_bytes("KRMOD_STRINGS_BLOB", exe.read(STRINGS_FILE))
            text = lua.run(_WALKER, "=strings", want_result=True) or b""
    except Exception:
        return GameNames()
    strings = {}
    for line in text.decode("utf-8", "replace").split("\n"):
        key, sep, value = line.partition("\t")
        if sep:
            strings[key] = value
    return GameNames(strings)
