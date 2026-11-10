"""Application data paths and persisted user settings.

Settings live in ``data/settings.json`` next to the project (or next to
the executable when frozen with PyInstaller), which keeps the app fully
portable and inspectable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULTS: dict = {
    "animation_speed": 1.0,      # multiplier: 0.4 = slow, 2.5 = fast
    "scramble_length": 25,
    "show_face_labels": True,
    "solver_engine": "auto",     # auto | kociemba | lbl
}


def data_dir() -> Path:
    """Directory for settings/statistics (created on demand)."""
    if getattr(sys, "frozen", False):  # PyInstaller executable
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    path = base / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Settings:
    """Small JSON-backed settings store with change callbacks."""

    def __init__(self) -> None:
        self._path = data_dir() / "settings.json"
        self._values: dict = dict(DEFAULTS)
        self._listeners: list = []
        self.load()

    # -- persistence ---------------------------------------------------------

    def load(self) -> None:
        try:
            if self._path.exists():
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                for key, default in DEFAULTS.items():
                    if key in stored:
                        self._values[key] = stored[key]
        except (OSError, json.JSONDecodeError):
            # Corrupt file: fall back to defaults, keep it from crashing.
            self._values = dict(DEFAULTS)

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._values, indent=2), encoding="utf-8"
            )
        except OSError:
            pass  # settings are non-critical; never crash the app for them

    # -- access ----------------------------------------------------------------

    def get(self, key: str):
        return self._values.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self._values[key] = value
        self.save()
        for listener in self._listeners:
            listener(key, value)

    def on_change(self, listener) -> None:
        self._listeners.append(listener)
