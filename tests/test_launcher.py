import dataclasses
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

    def fake_popen(cmd, cwd=None, creationflags=0):
        calls.append({"cmd": cmd, "cwd": cwd, "creationflags": creationflags})
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


def test_game_exe_name():
    assert GAME_EXE_NAME == "Kingdom Rush Genesis.exe"
