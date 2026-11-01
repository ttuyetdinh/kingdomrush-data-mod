"""Serialise plain Python values as Lua table constructors for the mod data files."""
from __future__ import annotations

import math
import re

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_KEYWORDS = frozenset(
    "and break do else elseif end false for function if in local nil not or repeat return then true until while".split()
)
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\0": "\\000"}


def _string(text: str) -> str:
    return '"' + "".join(_ESCAPES.get(ch, ch) for ch in text) + '"'


def _key(key: object) -> str:
    if isinstance(key, str):
        if _IDENT.match(key) and key not in _KEYWORDS:
            return key
        return f"[{_string(key)}]"
    if isinstance(key, int) and not isinstance(key, bool):
        return f"[{key}]"
    raise TypeError(f"unsupported Lua table key: {key!r}")


def to_lua(obj: object) -> str:
    if obj is None:
        return "nil"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite number cannot be written as Lua: {obj!r}")
        return repr(obj)
    if isinstance(obj, str):
        return _string(obj)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        return "{ " + ", ".join(f"{_key(k)} = {to_lua(v)}" for k, v in obj.items()) + " }"
    if isinstance(obj, (list, tuple)):
        if not obj:
            return "{}"
        return "{ " + ", ".join(to_lua(v) for v in obj) + " }"
    raise TypeError(f"cannot convert {type(obj).__name__} to Lua")
