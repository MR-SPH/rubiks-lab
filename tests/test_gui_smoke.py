"""Offscreen GUI integration tests.

These run the real MainWindow on the Qt offscreen platform and exercise
the full pipelines: animated moves -> logical state, scramble, solver
playback, undo, reset, practice timing and statistics.

Run with:  python -m pytest tests/test_gui_smoke.py -q
(QT_QPA_PLATFORM=offscreen is forced by the session fixture.)
"""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.cube import CubeState  # noqa: E402
from core.moves import Move, invert_sequence, parse_sequence  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp, monkeypatch, tmp_path):
    """A MainWindow with data paths redirected to a temp folder."""
    import services.statistics as stats_mod
    import services.settings as settings_mod

    monkeypatch.setattr(stats_mod, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(settings_mod, "data_dir", lambda: tmp_path)

    from ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    qapp.processEvents()


def pump(qapp, seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def wait_idle(qapp, win, timeout: float = 30.0) -> None:
    deadline = time.perf_counter() + timeout
    while win.view.is_animating and time.perf_counter() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    pump(qapp, 0.05)


def test_window_constructs(window):
    assert window.windowTitle().startswith("RUBIK'S LAB")
    assert window.state.is_solved()
    assert window.info_panel.timer_label.text() == "00:00.00"


def test_single_move_animation_pipeline(qapp, window):
    """A move goes through animation, then updates the logical state."""
    window.request_move(Move("R", 1), "user")
    assert window.view.is_animating
    wait_idle(qapp, window)
    assert not window.state.is_solved()
    assert window.moves_count == 1
    assert window.last_move_text == "R"
    # the view must render the post-move state (no pending work)
    assert window.view.animator.active is None


def test_move_then_inverse_restores(qapp, window):
    window.request_move(Move("F", 2), "user")
    wait_idle(qapp, window)
    window.request_move(Move("F", 2), "user")
    wait_idle(qapp, window)
    assert window.state.is_solved()


def test_scramble_fills_history_and_resets_counter(qapp, window):
    window._do_scramble()
    wait_idle(qapp, window)
    assert len(window.scramble_history) == 1
    assert len(window.scramble_history[0]) == window.settings.get("scramble_length")
    assert window.moves_count == 0
    assert not window.state.is_solved()
    from core.cube_validator import validate

    validate(window.state)  # scramble must keep the cube legal
    assert window._timer_state == "armed"  # practice timer waits for a move


def test_undo_takes_back_last_move(qapp, window):
    window.request_move(Move("L", 1), "user")
    wait_idle(qapp, window)
    window.request_move(Move("U", 1), "user")
    wait_idle(qapp, window)
    assert window.moves_count == 2
    window._do_undo()
    wait_idle(qapp, window)
    assert window.moves_count == 1
    assert window.user_history[-1] == Move("L", 1)
    window._do_undo()
    wait_idle(qapp, window)
    assert window.moves_count == 0
    assert window.state.is_solved()
    assert not window.control_panel.btn_undo.isEnabled()


def test_reset_clears_everything(qapp, window):
    window._do_scramble()
    wait_idle(qapp, window)
    window._do_reset()
    pump(qapp, 0.1)
    assert window.state.is_solved()
    assert window.moves_count == 0
    assert window.user_history == []
    assert window._timer_state == "idle"
    assert not window.view.is_animating


def test_solver_produces_and_plays_solution(qapp, window):
    window._do_scramble()
    wait_idle(qapp, window)
    n_moves = len(window.solution) if window.solution else 0
    window._do_solve("lbl")  # deterministic built-in engine for tests
    deadline = time.perf_counter() + 60
    while window._worker is not None and window._worker.isRunning():
        qapp.processEvents()
        time.sleep(0.02)
    pump(qapp, 0.2)
    assert window.solution, "solver must produce a solution"
    # progress widgets live on the Solver tab (may not be the active tab,
    # so check visibility relative to the panel, not the whole window)
    assert window.solver_panel.progress.isVisibleTo(window.solver_panel)
    assert window.solver_panel.progress.maximum() == len(window.solution)

    # play the whole solution through the animation pipeline
    window._toggle_playback()
    assert window._playing
    deadline = time.perf_counter() + 120
    while window.playback_index < len(window.solution) and time.perf_counter() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    wait_idle(qapp, window)
    assert window.playback_index == len(window.solution)
    assert window.state.is_solved()
    assert not window._playing


def test_playback_step_button(qapp, window):
    window.state.apply_sequence(parse_sequence("R U"))
    window._do_solve("lbl")
    deadline = time.perf_counter() + 60
    while window._worker is not None and window._worker.isRunning():
        qapp.processEvents()
        time.sleep(0.02)
    pump(qapp, 0.2)
    assert window.solution
    before = window.playback_index
    window._do_step()
    wait_idle(qapp, window)
    assert window.playback_index == before + 1


def test_user_move_stops_playback(qapp, window):
    window.state.apply_sequence(parse_sequence("R U"))
    window._do_solve("lbl")
    deadline = time.perf_counter() + 60
    while window._worker is not None and window._worker.isRunning():
        qapp.processEvents()
        time.sleep(0.02)
    pump(qapp, 0.2)
    window._toggle_playback()
    pump(qapp, 0.15)
    # a user move must stop the playback safely
    window.request_move(Move("U", 1), "user")
    assert not window._playing
    wait_idle(qapp, window)
    from core.cube_validator import validate

    validate(window.state)


def test_practice_mode_records_statistics(qapp, window, monkeypatch):
    recorded = {}

    def fake_completion(record):
        recorded.update(record)

    monkeypatch.setattr(window, "_show_completion", fake_completion)
    window._set_mode("practice")
    window._do_scramble()
    wait_idle(qapp, window)
    assert window._timer_state == "armed"
    # solve by replaying the inverse of the scramble, as a user would
    for move in invert_sequence(window.scramble_history[-1]):
        window.request_move(move, "user")
        wait_idle(qapp, window)
    assert window._timer_state == "finished"
    assert recorded.get("moves") == window.moves_count
    assert recorded.get("ms", 0) > 0
    assert window.stats.count() == 1
    assert window.stats_panel.table.rowCount() == 1


def test_free_play_solved_shows_status(qapp, window):
    window._set_mode("free")
    window.request_move(Move("R", 1), "user")
    wait_idle(qapp, window)
    window.request_move(Move("R", 3), "user")
    wait_idle(qapp, window)
    assert window.state.is_solved()
    assert window._timer_state == "idle"  # free play never runs the timer


def test_mode_switching(window):
    for mode in ("practice", "solver", "free"):
        window._set_mode(mode)
        assert window.mode == mode
        assert window.mode_switch.current == mode

    # Clicking the physical segmented buttons directly
    for mode in ("practice", "solver", "free"):
        window.mode_switch.button(mode).click()
        assert window.mode == mode
        assert window.mode_switch.current == mode


def test_settings_round_trip(window, tmp_path):
    window.settings.set("animation_speed", 1.7)
    window.settings.set("scramble_length", 12)
    # a fresh Settings instance must see the saved values
    from services.settings import Settings

    s2 = Settings()
    assert s2.get("animation_speed") == 1.7
    assert s2.get("scramble_length") == 12


def test_drag_request_signal(qapp, window):
    """The view's drag pipeline maps a direction to the right move."""
    view = window.view
    cubie = window.state.cubie_at((1, 1, 1))
    assert cubie is not None
    # drag right -> should pick a move rotating about y (U) or z (F)
    move = view._drag_direction_move(40, 0, {
        "home": (1, 1, 1),
        "cubie_pos": (1, 1, 1),
        "world_center": __import__("numpy").array([1.0, 1.0, 1.0]),
    })
    assert move is not None
    assert move.face in ("U", "F", "R")

    # drag left (opposite) -> should produce an inverse/counter-clockwise move
    move_rev = view._drag_direction_move(-40, 0, {
        "home": (1, 1, 1),
        "cubie_pos": (1, 1, 1),
        "world_center": __import__("numpy").array([1.0, 1.0, 1.0]),
    })
    assert move_rev is not None
    assert move_rev.face == move.face
    assert move_rev.turns != move.turns


def test_control_panel_button_cursors(window):
    from PySide6.QtCore import Qt
    for b in (window.control_panel.btn_scramble,
              window.control_panel.btn_undo,
              window.control_panel.btn_reset):
        assert b.cursor().shape() == Qt.PointingHandCursor


def test_cubie_view_renders_after_many_moves(qapp, window):
    """120 queued quick moves must end with visuals == logical state."""
    import random as _random

    rng = _random.Random(5)
    moves = [Move(rng.choice("UDLRFB"), rng.choice([1, 2, 3])) for _ in range(120)]
    # feed in chunks so the queue-overflow guard never drops moves
    i = 0
    while i < len(moves):
        while window.view.animator.pending > 24:
            qapp.processEvents()
            time.sleep(0.005)
        window.request_move(moves[i], "user", duration_ms=1.0)
        i += 1
    wait_idle(qapp, window, timeout=120)
    expected = CubeState()
    expected.apply_sequence(moves)
    assert window.state == expected
    # and the renderer produces quads without errors
    quads = window.view.renderer.build_scene(window.state)
    assert len(quads) > 100
