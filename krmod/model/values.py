"""Value types shared by the reader, the profile store and the UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KeyPath = tuple[str | int, ...]

_DAMAGE_SKIP = {
    "DAMAGE_ALL",
    "DAMAGE_ALL_FLAGS",
    "DAMAGE_ALL_TYPES",
    "DAMAGE_BASE_TYPES",
    "DAMAGE_NONE",
}


def path_str(p: KeyPath) -> str:
    return ".".join(str(seg) for seg in p)


@dataclass(frozen=True)
class Leaf:
    path: KeyPath
    value: float | str | bool
    kind: Literal["num", "str", "bool"]

    @property
    def is_enum(self) -> bool:
        last = self.path[-1] if self.path else None
        return (
            self.kind == "num"
            and isinstance(last, str)
            and (last == "damage_type" or last.endswith("_damage_type"))
        )

    @property
    def is_whole(self) -> bool:
        return self.kind == "num" and float(self.value) == int(self.value)


@dataclass
class BalanceTree:
    leaves: dict[KeyPath, Leaf]
    aliases: dict[KeyPath, KeyPath]
    damage_flags: dict[str, int]
    table_count: int

    def numeric(self) -> list[Leaf]:
        nums = [leaf for leaf in self.leaves.values() if leaf.kind == "num"]
        return sorted(nums, key=lambda leaf: path_str(leaf.path))

    def original(self, p: KeyPath) -> float:
        return float(self.leaves[p].value)


def decode_damage_type(value: int, flags: dict[str, int]) -> str:
    bits: dict[int, str] = {}
    for key, bit in flags.items():
        if not key.startswith("DAMAGE_") or key in _DAMAGE_SKIP:
            continue
        if bit > 0 and bit & (bit - 1) == 0:
            bits[bit] = key[len("DAMAGE_"):].lower().replace("_", " ").capitalize()
    names = [bits[bit] for bit in sorted(bits) if value & bit]
    return " + ".join(names) if names else "None"
