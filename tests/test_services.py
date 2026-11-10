"""Unit tests for services: Statistics and Settings."""

import json
from pathlib import Path

import pytest

from services.settings import Settings, DEFAULTS
from services.statistics import Statistics, format_time, format_ms


def test_statistics_record_and_summary(tmp_path: Path):
    path = tmp_path / "stats.json"
    stats = Statistics(path)
    assert stats.count() == 0
    assert stats.best() is None
    assert stats.mean() is None
    assert stats.summary()["ao5"] is None

    # Record 5 solves: 10s, 12s, 14s, 16s, 18s (in ms)
    # sorted: 10, 12, 14, 16, 18
    # ao5 drops best (10) and worst (18), mean of [12, 14, 16] = 14.0
    for ms in (10000, 12000, 14000, 16000, 18000):
        stats.record_solve(ms, 30)

    assert stats.count() == 5
    assert stats.best() == 10.0
    assert stats.mean() == 14.0
    assert stats.trimmed_average(5) == 14.0
    assert stats.summary()["ao5"] == 14.0
    assert stats.summary()["ao12"] is None


def test_statistics_ao12_wca_standard(tmp_path: Path):
    path = tmp_path / "stats.json"
    stats = Statistics(path)

    # 12 solves: 10..21 seconds
    # times = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
    # best: 10, worst: 21
    # middle 10: 11..20, mean = 15.5
    for sec in range(10, 22):
        stats.record_solve(sec * 1000, 40)

    assert stats.count() == 12
    assert stats.trimmed_average(12) == 15.5
    assert stats.summary()["ao12"] == 15.5


def test_statistics_clear_and_persistence(tmp_path: Path):
    path = tmp_path / "stats.json"
    stats = Statistics(path)
    stats.record_solve(15000, 30)
    assert stats.count() == 1

    # Reload from disk
    stats2 = Statistics(path)
    assert stats2.count() == 1
    assert stats2.best() == 15.0

    stats2.clear()
    assert stats2.count() == 0

    stats3 = Statistics(path)
    assert stats3.count() == 0


def test_format_time_and_ms():
    assert format_time(None) == "--:--.--"
    assert format_time(0.0) == "00:00.00"
    assert format_time(65.42) == "01:05.42"
    assert format_ms(None) == "--:--.--"
    assert format_ms(125340) == "02:05.34"


def test_settings_load_save_callback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("services.settings.data_dir", lambda: tmp_path)
    s = Settings()
    assert s.get("animation_speed") == DEFAULTS["animation_speed"]

    events = []
    s.on_change(lambda k, v: events.append((k, v)))

    s.set("animation_speed", 2.2)
    assert s.get("animation_speed") == 2.2
    assert events == [("animation_speed", 2.2)]

    # New instance loads saved value
    s2 = Settings()
    assert s2.get("animation_speed") == 2.2

