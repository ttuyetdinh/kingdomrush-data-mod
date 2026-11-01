"""Game process detection and launching."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import subprocess

import psutil

from krmod.model.values import BalanceTree
from krmod.modgen.writer import ApplyResult, apply_mod
from krmod.paths import GamePaths
from krmod.profiles import Profile

GAME_EXE_NAME = "Kingdom Rush Genesis.exe"


@dataclass(frozen=True)
class RunningGame:
    pid: int
    modded: bool


class RunOutcome(Enum):
    LAUNCHED = "LAUNCHED"
    UPDATED_RUNNING = "UPDATED_RUNNING"
    NEEDS_RESTART = "NEEDS_RESTART"


def find_game(paths: GamePaths) -> RunningGame | None:
    try:
        target_exe = paths.exe.resolve()
    except (OSError, ValueError):
        target_exe = paths.exe

    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            info = proc.info
            exe_str = info.get("exe")
            if not exe_str:
                continue
            try:
                proc_exe = Path(exe_str).resolve()
            except (OSError, ValueError):
                proc_exe = Path(exe_str)

            if proc_exe == target_exe:
                cmdline = info.get("cmdline") or []
                modded = "-balance_override" in cmdline
                return RunningGame(pid=proc.pid, modded=modded)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def launch(paths: GamePaths) -> int:
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP

    cmd = [str(paths.exe), "-balance_override", "mods.kr_mod"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(paths.game_dir),
        creationflags=flags,
    )
    return proc.pid


def apply_and_run(
    paths: GamePaths, profile: Profile, tree: BalanceTree
) -> tuple[RunOutcome, ApplyResult]:
    result = apply_mod(paths, profile, tree)
    running = find_game(paths)
    if running is None:
        launch(paths)
        return RunOutcome.LAUNCHED, result
    if running.modded:
        return RunOutcome.UPDATED_RUNNING, result
    return RunOutcome.NEEDS_RESTART, result
