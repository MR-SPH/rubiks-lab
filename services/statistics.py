"""Solve statistics: persistence and aggregation.

Records one entry per completed practice solve: timestamp, elapsed time,
move count and derived TPS.  Provides standard speedcubing aggregates
(best, mean, ao5/ao12 trimmed averages) over the stored history.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .settings import data_dir

MAX_RECORDS = 2000


class Statistics:
    """JSON-backed solve history."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (data_dir() / "stats.json")
        self._records: list[dict] = []
        self.load()

    # -- persistence ----------------------------------------------------------

    def load(self) -> None:
        try:
            if self._path.exists():
                self._records = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(self._records, list):
                    self._records = []
        except (OSError, json.JSONDecodeError):
            self._records = []

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._records[-MAX_RECORDS:], indent=1),
                encoding="utf-8",
            )
        except OSError:
            pass

    # -- recording -----------------------------------------------------------------

    def record_solve(self, time_ms: int, moves: int, mode: str = "practice") -> dict:
        tps = (moves / (time_ms / 1000.0)) if time_ms > 0 else 0.0
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ms": int(time_ms),
            "moves": int(moves),
            "tps": round(tps, 2),
            "mode": mode,
        }
        self._records.append(entry)
        self.save()
        return entry

    def clear(self) -> None:
        self._records.clear()
        self.save()

    # -- aggregation ------------------------------------------------------------------

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    def times(self, count: int | None = None) -> list[float]:
        recs = self._records if count is None else self._records[-count:]
        return [r["ms"] / 1000.0 for r in recs if r.get("ms", 0) > 0]

    def count(self) -> int:
        return len(self._records)

    def best(self) -> float | None:
        times = self.times()
        return min(times) if times else None

    def mean(self, count: int | None = None) -> float | None:
        times = self.times(count)
        return statistics.mean(times) if times else None

    def trimmed_average(self, window: int) -> float | None:
        """Speedcubing ``aoN``: mean of the last N solves, dropping the
        single best and worst solves (WCA standard for ao5, ao12, etc.)."""
        times = self.times(window)
        if len(times) < window or window < 3:
            return None
        middle = sorted(times)[1:-1]
        return statistics.mean(middle) if middle else None

    def summary(self) -> dict:
        return {
            "count": self.count(),
            "best": self.best(),
            "mean": self.mean(),
            "ao5": self.trimmed_average(5),
            "ao12": self.trimmed_average(12),
        }

    def recent(self, n: int = 10) -> list[dict]:
        return list(reversed(self._records[-n:]))


def format_time(seconds: float | None) -> str:
    """mm:ss.cc formatting used across the UI."""
    if seconds is None:
        return "--:--.--"
    total = max(0.0, seconds)
    minutes = int(total // 60)
    secs = total - minutes * 60
    return f"{minutes:02d}:{secs:05.2f}"


def format_ms(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "--:--.--"
    return format_time(milliseconds / 1000.0)
