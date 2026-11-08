"""Named profiles: changes-only edits, live settings and speed keys, stored as JSON."""
from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from krmod.model.stepping import (
    ENEMY_VALUES,
    EXTRA_POINTS_MAX,
    TROOP_MAX,
    TROOP_MIN,
    clamp_troop,
    snap_enemy,
)
from krmod.model.values import BalanceTree, KeyPath

FORBIDDEN_KEYS = frozenset(
    {"f1", "f2", "f3", "space", "escape", "return", "up", "down", "left", "right"}
)

_FORMAT_VERSION = 1
_ACTIVE_FILE = "_active.json"
_DEFAULT_NAME = "Default"
# Profile fields saved under "rules" and written to kr_mod_data.lua, with their defaults.
RULE_DEFAULTS: dict[str, bool | int] = {
    "unlock_tower_levels": False,
    "unlock_heroes": False,
    "unlock_towers": False,
    "unlock_spells": False,
    "allow_both_paths": False,
    "extra_hero_points": 0,
    "extra_spell_points": 0,
    "extra_upgrade_points": 0,
}


class ProfileError(ValueError):
    pass


def _is_number(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_finite_number(x: object) -> bool:
    if not _is_number(x):
        return False
    try:
        return math.isfinite(x)
    except OverflowError:
        return False


@dataclass
class LiveSettings:
    speed: int = 1
    enemy_mult: float = 1.0
    troop_delta: int = 0

    def validate(self) -> None:
        if isinstance(self.speed, bool) or not isinstance(self.speed, int) or self.speed not in (1, 2, 3):
            raise ProfileError(f"speed must be 1, 2 or 3, got {self.speed!r}")
        if not _is_finite_number(self.enemy_mult):
            raise ProfileError(f"enemy_mult must be a number, got {self.enemy_mult!r}")
        if self.enemy_mult not in ENEMY_VALUES:
            raise ProfileError(f"enemy_mult must be 0.25 or a whole number from 1 to 10, got {self.enemy_mult!r}")
        if isinstance(self.troop_delta, bool) or not isinstance(self.troop_delta, int):
            raise ProfileError(f"troop_delta must be a whole number, got {self.troop_delta!r}")
        if not TROOP_MIN <= self.troop_delta <= TROOP_MAX:
            raise ProfileError(f"troop_delta must be between {TROOP_MIN} and {TROOP_MAX}, got {self.troop_delta!r}")


# LOVE 11 KeyConstant names (love.keyboard.isDown / love.keypressed).
LOVE_KEYS = frozenset(
    set("abcdefghijklmnopqrstuvwxyz0123456789")
    | set("!\"#$&'()*+,-./:;<=>?@[\\]^_`")
    | {f"kp{d}" for d in range(10)}
    | {f"f{n}" for n in range(1, 20)}
    | {
        "space", "kp.", "kp,", "kp/", "kp*", "kp-", "kp+", "kpenter", "kp=",
        "up", "down", "right", "left", "home", "end", "pageup", "pagedown",
        "insert", "backspace", "tab", "clear", "return", "delete",
        "numlock", "capslock", "scrolllock",
        "rshift", "lshift", "rctrl", "lctrl", "ralt", "lalt", "rgui", "lgui", "mode",
        "www", "mail", "calculator", "computer", "appsearch", "apphome", "appback",
        "appforward", "apprefresh", "appbookmarks", "currencyunit", "undo",
        "application", "power", "menu", "help", "sysreq", "pause", "escape",
    }
)


def validate_speed_keys(keys: Sequence[str]) -> tuple[str, str, str]:
    if isinstance(keys, str) or len(keys) != 3:
        raise ProfileError("exactly 3 speed keys are required")
    out: list[str] = []
    for key in keys:
        if not isinstance(key, str):
            raise ProfileError(f"invalid key name {key!r}")
        norm = key.strip().lower()
        if norm not in LOVE_KEYS:
            raise ProfileError(f"{key!r} is not a LOVE key name")
        if norm in FORBIDDEN_KEYS:
            raise ProfileError(f"key {norm!r} is reserved and cannot be a speed key")
        out.append(norm)
    if len(set(out)) != 3:
        raise ProfileError("speed keys must be 3 distinct keys")
    return out[0], out[1], out[2]


@dataclass
class Profile:
    name: str
    changes: dict[KeyPath, float] = field(default_factory=dict)
    unlock_tower_levels: bool = False
    unlock_heroes: bool = False
    unlock_towers: bool = False
    unlock_spells: bool = False
    allow_both_paths: bool = False
    extra_hero_points: int = 0
    extra_spell_points: int = 0
    extra_upgrade_points: int = 0
    live: LiveSettings = field(default_factory=LiveSettings)
    speed_keys: tuple[str, str, str] = ("f5", "f6", "f7")


def stale_changes(profile: Profile, tree: BalanceTree) -> list[KeyPath]:
    stale: list[KeyPath] = []
    for path in profile.changes:
        leaf = tree.leaves.get(path)
        if leaf is None or leaf.kind != "num" or leaf.is_enum:
            stale.append(path)
    return stale


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"

def _clean_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ProfileError("profile name must not be empty")
    return name.strip()


def rules_dict(profile: Profile) -> dict[str, bool | int]:
    """The profile's rules, as saved in the profile JSON and in kr_mod_data.lua."""
    return {name: getattr(profile, name) for name in RULE_DEFAULTS}


def validate_rule(name: str, value: object) -> None:
    if name not in RULE_DEFAULTS:
        raise ProfileError(f"unknown rule {name!r}")
    if isinstance(RULE_DEFAULTS[name], bool):
        if not isinstance(value, bool):
            raise ProfileError(f"{name} must be true or false")
    elif isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= EXTRA_POINTS_MAX:
        raise ProfileError(f"{name} must be a whole number from 0 to {EXTRA_POINTS_MAX}, got {value!r}")


def _validate_profile(profile: Profile) -> None:
    profile.live.validate()
    validate_speed_keys(profile.speed_keys)
    for name, value in rules_dict(profile).items():
        validate_rule(name, value)
    for path, value in profile.changes.items():
        if not isinstance(path, tuple) or not path or not all(
            isinstance(seg, (str, int)) and not isinstance(seg, bool) for seg in path
        ):
            raise ProfileError(f"invalid change path {path!r}")
        if not _is_finite_number(value):
            raise ProfileError(f"invalid change value for {path!r}: {value!r}")


def _to_json(profile: Profile) -> dict:
    return {
        "version": _FORMAT_VERSION,
        "name": profile.name,
        "changes": [
            {"path": list(path), "value": value} for path, value in profile.changes.items()
        ],
        "rules": rules_dict(profile),
        "live": {
            "speed": profile.live.speed,
            "enemy_mult": profile.live.enemy_mult,
            "troop_delta": profile.live.troop_delta,
        },
        "speed_keys": list(profile.speed_keys),
    }


def _snap_enemy_setting(value: object) -> object:
    """Finite numbers snap to the allowed list; anything else is left for validate() to reject."""
    return snap_enemy(value) if _is_finite_number(value) else value


def _clamp_troop_setting(value: object) -> object:
    return clamp_troop(value) if _is_finite_number(value) else value


def _from_json(data: object) -> Profile:
    if not isinstance(data, dict):
        raise ProfileError("not a JSON object")
    if data.get("version") != _FORMAT_VERSION:
        raise ProfileError(f"unsupported version {data.get('version')!r}")
    name = _clean_name(data.get("name"))
    raw_changes = data.get("changes", [])
    if not isinstance(raw_changes, list):
        raise ProfileError("changes must be a list")
    changes: dict[KeyPath, float] = {}
    for entry in raw_changes:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), list):
            raise ProfileError("malformed change entry")
        segments = entry["path"]
        if not segments or not all(
            isinstance(seg, (str, int)) and not isinstance(seg, bool) for seg in segments
        ):
            raise ProfileError(f"invalid change path {segments!r}")
        changes[tuple(segments)] = entry.get("value")
    rules = data.get("rules", {})
    live = data.get("live", {})
    if not isinstance(rules, dict) or not isinstance(live, dict):
        raise ProfileError("rules and live must be objects")
    rule_values = {name: rules.get(name, default) for name, default in RULE_DEFAULTS.items()}
    keys = data.get("speed_keys", ["f5", "f6", "f7"])
    if not isinstance(keys, list):
        raise ProfileError("speed_keys must be a list")
    profile = Profile(
        name=name,
        changes=changes,
        **rule_values,
        live=LiveSettings(
            live.get("speed", 1),
            _snap_enemy_setting(live.get("enemy_mult", 1.0)),
            _clamp_troop_setting(live.get("troop_delta", 0)),
        ),
        speed_keys=validate_speed_keys(keys),
    )
    _validate_profile(profile)
    return profile


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ProfileError(f"cannot remove {path.name}: {exc}") from exc


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _atomic_write_json(path: Path, data: object) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.stem + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ProfileStore:
    def __init__(self, dir: Path) -> None:
        self.dir = Path(dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.load_warnings: list[str] = []
        self._profiles: dict[str, Profile] = {}  # keyed by name.lower()
        self._files: dict[str, Path] = {}
        self._active_key = ""
        self._load()

    # ---- loading -------------------------------------------------------

    def _load(self) -> None:
        for path in sorted(self.dir.glob("*.json"), key=lambda p: p.name.lower()):
            if path.name == _ACTIVE_FILE:
                continue
            try:
                profile = _from_json(json.loads(path.read_text(encoding="utf-8")))
                key = profile.name.lower()
                if key in self._profiles:
                    raise ProfileError(f"duplicate profile name {profile.name!r}")
            except (OSError, ValueError, RecursionError) as exc:
                self.load_warnings.append(f"{path.name}: {exc}")
                continue
            self._profiles[key] = profile
            self._files[key] = path
        if not self._profiles:
            self._add_default()
        wanted = self._read_active_name()
        if wanted is not None and wanted.lower() in self._profiles:
            self._active_key = wanted.lower()
        else:
            self._active_key = self._sorted_keys()[0]
            self._write_active()

    def _read_active_name(self) -> str | None:
        try:
            data = json.loads((self.dir / _ACTIVE_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        name = data.get("active") if isinstance(data, dict) else None
        return name if isinstance(name, str) else None

    def _write_active(self) -> None:
        _atomic_write_json(
            self.dir / _ACTIVE_FILE, {"active": self._profiles[self._active_key].name}
        )

    # ---- helpers -------------------------------------------------------

    def _sorted_keys(self) -> list[str]:
        return sorted(self._profiles, key=lambda k: (k, self._profiles[k].name))

    def _key(self, name: str) -> str:
        key = name.strip().lower() if isinstance(name, str) else ""
        if key not in self._profiles:
            raise ProfileError(f"no such profile: {name!r}")
        return key

    def _check_new(self, name: str, own_key: str | None = None) -> tuple[str, Path]:
        name = _clean_name(name)
        key = name.lower()
        if key in self._profiles and key != own_key:
            raise ProfileError(f"profile {name!r} already exists")
        path = self.dir / f"{slug(name)}.json"
        if path.name == _ACTIVE_FILE:
            raise ProfileError(f"profile name {name!r} is reserved")
        if path.exists() and not (own_key is not None and self._files.get(own_key) == path):
            raise ProfileError(f"a file for {name!r} already exists: {path.name}")
        return name, path

    def _free_path(self, slug: str, reuse: Path | None = None) -> Path:
        n = 1
        while True:
            path = self.dir / (f"{slug}.json" if n == 1 else f"{slug}-{n}.json")
            if path == reuse or not path.exists():
                return path
            n += 1

    def _add_default(self) -> None:
        profile = Profile(_DEFAULT_NAME)
        path = self._free_path(slug(_DEFAULT_NAME))
        _atomic_write_json(path, _to_json(profile))
        self._profiles[_DEFAULT_NAME.lower()] = profile
        self._files[_DEFAULT_NAME.lower()] = path

    def _add(self, profile: Profile) -> Profile:
        name, path = self._check_new(profile.name)
        profile.name = name
        _validate_profile(profile)
        _atomic_write_json(path, _to_json(profile))
        self._profiles[name.lower()] = profile
        self._files[name.lower()] = path
        return profile

    # ---- public API ----------------------------------------------------

    def names(self) -> list[str]:
        return [self._profiles[k].name for k in self._sorted_keys()]

    def active(self) -> Profile:
        return self._profiles[self._active_key]

    def switch(self, name: str) -> None:
        self._active_key = self._key(name)
        self._write_active()

    def create(self, name: str) -> Profile:
        return self._add(Profile(name))

    def duplicate(self, src: str, new: str) -> Profile:
        source = self._profiles[self._key(src)]
        copy_ = copy.deepcopy(source)
        copy_.name = new
        return self._add(copy_)

    def rename(self, old: str, new: str) -> None:
        key = self._key(old)
        name, path = self._check_new(new, own_key=key)
        profile = self._profiles[key]
        old_path = self._files[key]
        was_active = key == self._active_key
        updated = copy.deepcopy(profile)
        updated.name = name
        _atomic_write_json(path, _to_json(updated))
        if old_path != path:
            try:
                _unlink(old_path)
            except ProfileError:
                _unlink_quiet(path)
                raise
        profile.name = name
        del self._profiles[key], self._files[key]
        self._profiles[name.lower()] = profile
        self._files[name.lower()] = path
        if was_active:
            self._active_key = name.lower()
            self._write_active()

    def delete(self, name: str) -> None:
        key = self._key(name)
        was_active = key == self._active_key
        path = self._files[key]
        recreate = len(self._profiles) == 1
        if recreate:
            # Write the replacement Default first so a failure leaves the store intact.
            new_path = self._free_path(slug(_DEFAULT_NAME), reuse=path)
            _atomic_write_json(new_path, _to_json(Profile(_DEFAULT_NAME)))
            if new_path != path:
                try:
                    _unlink(path)
                except ProfileError:
                    _unlink_quiet(new_path)
                    raise
        else:
            _unlink(path)
        del self._profiles[key], self._files[key]
        if recreate:
            self._profiles[_DEFAULT_NAME.lower()] = Profile(_DEFAULT_NAME)
            self._files[_DEFAULT_NAME.lower()] = new_path
        if was_active or self._active_key not in self._profiles:
            self._active_key = self._sorted_keys()[0]
            self._write_active()

    def save(self, profile: Profile) -> None:
        key = self._key(profile.name)
        _validate_profile(profile)
        if self._profiles[key] is not profile:
            self._profiles[key] = profile
        profile.name = profile.name.strip()
        _atomic_write_json(self._files[key], _to_json(profile))
