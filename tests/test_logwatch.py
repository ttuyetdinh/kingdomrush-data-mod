from pathlib import Path
import time
import pytest

from krmod.modgen.logwatch import (
    LogSummary,
    LogWatcher,
    parse_log,
)


def test_parse_log():
    s = parse_log(
        "applied 3 changes\nmissing towers.x.price.1\nunlock stage1 mode 1: removed 15, kept 0\nerror boom\n"
    )
    assert (s.applied, s.missing, s.errors) == (
        3,
        ["towers.x.price.1"],
        ["boom"],
    ) and len(s.unlock) == 1


def test_parse_log_empty_and_extra():
    s = parse_log("")
    assert (s.applied, s.missing, s.unlock, s.errors, s.raw) == (
        None,
        [],
        [],
        [],
        "",
    )

    text = (
        "speed x2\n"
        "enemies x1.5\n"
        "troops x2.0: 3 barracks\n"
        "error second failure\n"
    )
    s2 = parse_log(text)
    assert s2.applied is None
    assert s2.errors == ["second failure"]
    assert s2.raw == text


def test_logwatch_ignores_old_log(tmp_path):
    log = tmp_path / "kr_mod_log.txt"
    log.write_text("applied 1 changes\n")
    w = LogWatcher(log)
    time.sleep(0.05)
    w.mark()
    assert w.poll() is None
    time.sleep(0.05)
    log.write_text("applied 2 changes\n")
    assert w.poll().applied == 2 and w.poll() is None


def test_logwatch_nonexistent_file(tmp_path):
    log = tmp_path / "absent.txt"
    w = LogWatcher(log)
    assert w.poll() is None


def test_logwatch_mark_resets_reported_mtime(tmp_path):
    log = tmp_path / "kr_mod_log.txt"
    w = LogWatcher(log)
    time.sleep(0.05)
    log.write_text("applied 1 changes\n")
    # Mark was at 0, file exists with mtime > 0
    s1 = w.poll()
    assert s1 is not None and s1.applied == 1
    assert w.poll() is None

    # Now mark at now
    time.sleep(0.05)
    w.mark()
    assert w.poll() is None

    # Write new content
    time.sleep(0.05)
    log.write_text("applied 5 changes\n")
    s2 = w.poll()
    assert s2 is not None and s2.applied == 5
    assert w.poll() is None
