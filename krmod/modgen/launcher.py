"""Game process detection and launching."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterator

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


@contextmanager
def _system_dll_search() -> Iterator[None]:
    """While a process is started: the system's DLL search, not the single-file exe's.

    The exe's bootloader points the DLL search at its unpack folder (SetDllDirectoryW) and
    processes started from it inherit that. The game then loads VCRUNTIME140.dll from
    runtime\\_MEI..., holds it for as long as it runs, and the exe cannot remove that folder when
    it closes ("Failed to remove temporary directory"). Restored afterwards for the app itself.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if sys.platform != "win32" or not bundle:
        yield
        return
    import ctypes

    set_dll_directory = ctypes.windll.kernel32.SetDllDirectoryW
    set_dll_directory(None)
    try:
        yield
    finally:
        set_dll_directory(bundle)


def _system_env() -> dict[str, str] | None:
    """os.environ without PATH entries inside the exe's unpack folder (None when not frozen)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return None
    root = os.path.normcase(os.path.abspath(bundle))
    env = dict(os.environ)
    keep = []
    for entry in env.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        path = os.path.normcase(os.path.abspath(entry))
        if path != root and not path.startswith(root + os.sep):
            keep.append(entry)
    env["PATH"] = os.pathsep.join(keep)
    return env


def launch(paths: GamePaths) -> int:
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP

    cmd = [str(paths.exe), "-balance_override", "mods.kr_mod"]
    with _system_dll_search():
        proc = subprocess.Popen(
            cmd,
            cwd=str(paths.game_dir),
            env=_system_env(),
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
