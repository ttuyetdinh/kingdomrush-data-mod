"""Write mod files atomically into the mods folder."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile
import time

from krmod.model.values import BalanceTree, KeyPath, path_str
from krmod.modgen.luafmt import to_lua
from krmod.paths import GamePaths
from krmod.profiles import (
    LiveSettings,
    Profile,
    rules_dict,
    stale_changes,
    validate_speed_keys,
)

LAUNCH_BAT = (
    '@echo off\r\n'
    'cd /d "%~dp0.."\r\n'
    'start "" "Kingdom Rush Genesis.exe" -balance_override mods.kr_mod\r\n'
)


def atomic_write(path: Path, text: str | bytes, retries: int = 5) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=path.stem + ".", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        if isinstance(text, bytes):
            with open(fd, "wb") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
        else:
            with open(fd, "w", encoding="utf-8", newline="") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())

        attempts = max(1, retries)
        for attempt in range(attempts):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.05)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def data_table(profile: Profile, tree: BalanceTree) -> dict:
    stale = set(stale_changes(profile, tree))
    valid: dict[KeyPath, float] = {}
    for p, v in profile.changes.items():
        if p in stale:
            continue
        leaf = tree.leaves.get(p)
        if leaf is not None and v == leaf.value:
            continue
        valid[p] = v

    sorted_paths = sorted(valid.keys(), key=path_str)
    changes = [{"p": list(p), "v": valid[p]} for p in sorted_paths]

    rules = rules_dict(profile)

    speed_keys = list(validate_speed_keys(profile.speed_keys))
    return {
        "version": 1,
        "changes": changes,
        "rules": rules,
        "speed_keys": speed_keys,
    }


_SEQ_RE = re.compile(r"\bseq = (\d+)")


def _existing_seq(path: Path) -> int | None:
    try:
        match = _SEQ_RE.search(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return int(match.group(1)) if match else None


def write_live(paths: GamePaths, live: LiveSettings, *, bump_seq: bool = False) -> None:
    """Write kr_mod_live.lua. The file carries a seq counter that the in-game poller watches:
    bump_seq (a speed button click) makes the game apply the file's speed again even when it
    equals the previous one; any other write keeps the counter it finds.
    """
    live.validate()
    path = paths.mods_dir / "kr_mod_live.lua"
    seq = _existing_seq(path)
    if bump_seq:
        seq = max((seq or 0) + 1, time.time_ns() // 1_000_000)
    seq_field = "" if seq is None else f", seq = {seq}"
    text = (
        f"return {{ speed = {live.speed}, "
        f"enemy_mult = {float(live.enemy_mult)!r}, "
        f"troop_delta = {int(live.troop_delta)}, "
        f"group_gap = {int(live.group_gap)}{seq_field} }}\n"
    )
    atomic_write(path, text)


@dataclass(frozen=True)
class ApplyResult:
    files: list[Path]
    applied: int
    stale: list[KeyPath]


def apply_mod(
    paths: GamePaths, profile: Profile, tree: BalanceTree
) -> ApplyResult:
    paths.mods_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    template_dir = paths.mod_template_dir
    if template_dir.is_dir():
        for src in sorted(template_dir.rglob("*.lua")):
            if src.is_file():
                rel = src.relative_to(template_dir)
                dest = paths.mods_dir / rel
                atomic_write(dest, src.read_bytes())
                written.append(dest)

    dt = data_table(profile, tree)
    data_path = paths.mods_dir / "kr_mod_data.lua"
    atomic_write(data_path, f"return {to_lua(dt)}\n")
    written.append(data_path)

    live_path = paths.mods_dir / "kr_mod_live.lua"
    write_live(paths, profile.live)
    written.append(live_path)

    bat_path = paths.mods_dir / "launch_modded.bat"
    atomic_write(bat_path, LAUNCH_BAT)
    written.append(bat_path)

    stale = stale_changes(profile, tree)
    applied = len(dt["changes"])
    return ApplyResult(files=written, applied=applied, stale=stale)
