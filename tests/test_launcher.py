import dataclasses
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from krmod.modgen import launcher
from krmod.modgen.launcher import (
    GAME_EXE_NAME,
    RunningGame,
    RunOutcome,
    apply_and_run,
    find_game,
    launch,
)
from krmod.profiles import LiveSettings, Profile


@pytest.fixture
def tmp_game(game_paths, tmp_path):
    exe = tmp_path / "Kingdom Rush Genesis.exe"
    exe.write_text("")
    mods_dir = tmp_path / "mods"
    return dataclasses.replace(
        game_paths,
        game_dir=tmp_path,
        exe=exe,
        mods_dir=mods_dir,
    )


def test_apply_and_run_outcomes(tmp_game, tree, monkeypatch):
    launched = []
    monkeypatch.setattr(launcher, "launch", lambda paths: launched.append(1) or 99)
    for running, outcome in (
        (RunningGame(1, True), RunOutcome.UPDATED_RUNNING),
        (RunningGame(1, False), RunOutcome.NEEDS_RESTART),
        (None, RunOutcome.LAUNCHED),
    ):
        monkeypatch.setattr(launcher, "find_game", lambda paths, r=running: r)
        assert (
            apply_and_run(
                tmp_game, Profile(name="T", changes={}, live=LiveSettings()), tree
            )[0]
            is outcome
        )
    assert launched == [1]


def test_find_game_reads_cmdline(tmp_game, monkeypatch):
    fake = SimpleNamespace(
        info={
            "name": "Kingdom Rush Genesis.exe",
            "exe": str(tmp_game.exe),
            "cmdline": [
                str(tmp_game.exe),
                "-balance_override",
                "mods.kr_mod",
            ],
        },
        pid=5,
    )
    monkeypatch.setattr(launcher.psutil, "process_iter", lambda attrs: [fake])
    assert find_game(tmp_game) == RunningGame(5, True)


def test_find_game_unmodded(tmp_game, monkeypatch):
    fake = SimpleNamespace(
        info={
            "name": "Kingdom Rush Genesis.exe",
            "exe": str(tmp_game.exe),
            "cmdline": [str(tmp_game.exe)],
        },
        pid=12,
    )
    monkeypatch.setattr(launcher.psutil, "process_iter", lambda attrs: [fake])
    assert find_game(tmp_game) == RunningGame(12, False)


def test_find_game_none_when_different_exe(tmp_game, monkeypatch):
    fake = SimpleNamespace(
        info={
            "name": "other.exe",
            "exe": str(tmp_game.game_dir / "other.exe"),
            "cmdline": ["other.exe"],
        },
        pid=15,
    )
    monkeypatch.setattr(launcher.psutil, "process_iter", lambda attrs: [fake])
    assert find_game(tmp_game) is None


def test_find_game_skips_inaccessible_processes(tmp_game, monkeypatch):
    class VanishedProcess:
        @property
        def info(self):
            raise launcher.psutil.NoSuchProcess(pid=99)

    class DeniedProcess:
        @property
        def info(self):
            raise launcher.psutil.AccessDenied(pid=100)

    class NoneExeProcess:
        info = {"name": "system", "exe": None, "cmdline": None}
        pid = 101

    real = SimpleNamespace(
        info={
            "name": "Kingdom Rush Genesis.exe",
            "exe": str(tmp_game.exe),
            "cmdline": [str(tmp_game.exe), "-balance_override", "mods.kr_mod"],
        },
        pid=102,
    )
    monkeypatch.setattr(
        launcher.psutil,
        "process_iter",
        lambda attrs: [VanishedProcess(), DeniedProcess(), NoneExeProcess(), real],
    )
    assert find_game(tmp_game) == RunningGame(102, True)


def test_launch_calls_popen(tmp_game, monkeypatch):
    calls = []

    def fake_popen(cmd, cwd=None, env=None, creationflags=0):
        calls.append({"cmd": cmd, "cwd": cwd, "env": env, "creationflags": creationflags})
        return SimpleNamespace(pid=42)

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    pid = launch(tmp_game)
    assert pid == 42
    assert len(calls) == 1
    assert calls[0]["cmd"] == [
        str(tmp_game.exe),
        "-balance_override",
        "mods.kr_mod",
    ]
    assert calls[0]["cwd"] == str(tmp_game.game_dir)
    assert calls[0]["env"] is None  # not the single-file exe: the app's own environment


@pytest.mark.skipif(sys.platform != "win32", reason="SetDllDirectoryW is Windows only")
def test_frozen_launch_gives_the_game_the_system_dll_search(tmp_game, tmp_path, monkeypatch):
    # The game must not load DLLs from the exe's unpack folder: it would hold them while it
    # runs and the exe could not remove that folder when it closes.
    import ctypes

    bundle = tmp_path / "runtime" / "_MEI123"
    events = []
    kernel32 = SimpleNamespace(SetDllDirectoryW=lambda path: events.append(("dll", path)))
    monkeypatch.setattr(ctypes.windll, "kernel32", kernel32, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bundle), str(bundle / "lib"), r"C:\Windows"]))

    def fake_popen(cmd, cwd=None, env=None, creationflags=0):
        events.append(("popen", env["PATH"]))
        return SimpleNamespace(pid=7)

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    assert launch(tmp_game) == 7
    assert events == [("dll", None), ("popen", r"C:\Windows"), ("dll", str(bundle))]
    assert os.environ["PATH"].startswith(str(bundle))  # the app's own PATH is untouched


def test_game_exe_name():
    assert GAME_EXE_NAME == "Kingdom Rush Genesis.exe"
