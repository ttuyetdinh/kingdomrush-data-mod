"""Parse and watch the mod runtime log."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time


@dataclass
class LogSummary:
    applied: int | None
    missing: list[str]
    unlock: list[str]
    errors: list[str]
    raw: str


def parse_log(text: str) -> LogSummary:
    applied: int | None = None
    missing: list[str] = []
    unlock: list[str] = []
    errors: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m_applied = re.match(r"^applied\s+(\d+)\s+changes$", line)
        if m_applied:
            applied = int(m_applied.group(1))
            continue
        if line.startswith("missing "):
            missing.append(line[len("missing "):].strip())
            continue
        if line.startswith("unlock "):
            unlock.append(line[len("unlock "):].strip())
            continue
        if line.startswith("error "):
            errors.append(line[len("error "):].strip())
            continue
        if line.startswith("error:"):
            errors.append(line[len("error:"):].strip())
            continue
        if line == "error":
            errors.append("error")
            continue

    return LogSummary(
        applied=applied,
        missing=missing,
        unlock=unlock,
        errors=errors,
        raw=text,
    )


class LogWatcher:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._mark: float = 0.0
        self._last_mtime: float | None = None

    def mark(self) -> None:
        self._mark = time.time()
        self._last_mtime = None

    def poll(self) -> LogSummary | None:
        try:
            stat = self.path.stat()
        except OSError:
            return None
        if stat.st_mtime <= self._mark:
            return None
        if self._last_mtime is not None and stat.st_mtime == self._last_mtime:
            return None
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        self._last_mtime = stat.st_mtime
        return parse_log(text)
