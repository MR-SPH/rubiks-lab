"""RUBIK'S LAB main window: layout, modes, session logic, solver playback.

Ownership of the logical cube state lives here.  The 3D view renders the
state and plays animations; every animated move reports back through
``moveCompleted`` and *only then* is the logical state updated, after
which the view is re-synced.  This makes the logical state the single
source of truth end to end.
"""

from __future__ import annotations

import random
import time

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.cube import CubeState
from core.cube_validator import validate, InvalidCubeError
from core.moves import Move, format_sequence
from core.scramble import random_scramble
from engine.cube_view import CubeView, SCRAMBLE_MOVE_MS
from services.settings import Settings
from services.statistics import Statistics
from solver.solver import (
    KOCIEMBA_AVAILABLE,
    SolveError,
    engine_label,
    solve as solve_state,
)
from solver.solution_player import SolutionPlayer
from .components import Badge, Card, LogoMark, ModeSwitch, StatTile
from .panels import ControlPanel, InfoPanel, SolverPanel, StatsPanel
from .themes import ACCENT, TEXT_FAINT, TEXT_MUTED

APP_VERSION = "1.0.0"

MOVE_DURATIONS = {"user": None, "undo": None, "scramble": SCRAMBLE_MOVE_MS,
                  "playback": None}

#: Keyboard: face -> (plain, shift, alt) turn counts.
_FACE_KEYS = ("U", "D", "L", "R", "F", "B")


class _SolverWorker(QThread):
    """Runs a solving engine off the UI thread."""

    solved = Signal(list, str)
    errored = Signal(str)

    def __init__(self, state: CubeState, engine: str, parent=None) -> None:
        super().__init__(parent)
        self._state = state  # a private clone; nobody else mutates it
        self._engine = engine

    def run(self) -> None:  # pragma: no cover - thread entry
        try:
            moves, engine = solve_state(self._state, self._engine)
            self.solved.emit(moves, engine)
        except (SolveError, InvalidCubeError, Exception) as exc:  # noqa: BLE001
            self.errored.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QWidget):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RUBIK'S LAB — 3D Cube Simulator & Solver")
        self.resize(1440, 900)
        self.setMinimumSize(1060, 660)

        # -- services & state -----------------------------------------------
        self.settings = Settings()
        self.stats = Statistics()
        self.state = CubeState()
        self.mode = "free"

        self.user_history: list[Move] = []
        self.scramble_history: list[list[Move]] = []
        self.moves_count = 0
        self.last_move_text = "--"

        # practice timer
        self._timer_state = "idle"     # idle | armed | running | finished
        self._timer_start = 0.0
        self._timer_value = 0.0
        self._final_time: float | None = None

        # solver
        self._worker: _SolverWorker | None = None
        self.player = SolutionPlayer()
        self._playing = False
        self._playback_speed = 1.0

        self._build_ui()
        self._build_shortcuts()
        self._connect()
        self._apply_settings_to_ui()
        self._refresh_all()
        self._set_status("Ready — drag a sticker or use the move buttons")

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        root.addWidget(self.splitter, 1)

        # 3D workspace
        self.view = CubeView(self.state)
        self.splitter.addWidget(self.view)

        # sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(372)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(12)

        self.info_panel = InfoPanel(self.state)
        side_layout.addWidget(self.info_panel)

        self.tabs = QTabWidget()
        self.control_panel = ControlPanel(
            int(self.settings.get("scramble_length"))
        )
        engine_opts = [("auto", "Auto engine")]
        if KOCIEMBA_AVAILABLE:
            engine_opts.append(("kociemba", "Kociemba two-phase"))
        engine_opts.append(("lbl", "Layer-by-layer"))
        self.solver_panel = SolverPanel(engine_opts)
        self.stats_panel = StatsPanel(self.stats)
        self.tabs.addTab(self.control_panel, "Play")
        self.tabs.addTab(self.solver_panel, "Solver")
        self.tabs.addTab(self.stats_panel, "Stats")
        side_layout.addWidget(self.tabs, 1)

        self.splitter.addWidget(sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # status bar
        self.statusBar = QFrame()
        self.statusBar.setObjectName("statusbar")
        status_layout = QHBoxLayout(self.statusBar)
        status_layout.setContentsMargins(14, 7, 14, 7)
        self.status_label = QLabel("")
        self.status_label.setObjectName("hint")
        self.hint_label = QLabel(
            "Drag stickers to turn · drag background to orbit · scroll to zoom"
        )
        self.hint_label.setObjectName("hint")
        self.shortcut_label = QLabel("S scramble · Z undo · X reset · Space play")
        self.shortcut_label.setObjectName("hint")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.hint_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.shortcut_label)
        root.addWidget(self.statusBar)

        # timers
        self._ui_timer = QTimer(self)
        self._ui_timer.start(100)

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(58)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        self.logo = LogoMark(30)
        layout.addWidget(self.logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        t = QLabel("RUBIK'S LAB")
        t.setObjectName("appTitle")
        s = QLabel("3D CUBE SIMULATOR & SOLVER")
        s.setObjectName("appSub")
        title_box.addWidget(t)
        title_box.addWidget(s)
        title_holder = QWidget()
        title_holder.setLayout(title_box)
        layout.addWidget(title_holder)
        layout.addSpacing(18)

        self.mode_switch = ModeSwitch(
            [("free", "Free Play"), ("practice", "Practice"), ("solver", "Solver")]
        )
        layout.addWidget(self.mode_switch)
        layout.addStretch(1)

        self.btn_panel = QPushButton("Panel")
        self.btn_panel.setObjectName("ghost")
        self.btn_panel.setCheckable(True)
        self.btn_panel.setChecked(True)
        self.btn_panel.setToolTip("Show or hide the side panel")
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setObjectName("ghost")
        self.btn_about = QPushButton("About")
        self.btn_about.setObjectName("ghost")
        for b in (self.btn_panel, self.btn_settings, self.btn_about):
            b.setCursor(Qt.PointingHandCursor)
            layout.addWidget(b)
        return bar

    def _build_shortcuts(self) -> None:
        def face_seq(face: str):
            QShortcut(QKeySequence(face), self,
                      activated=lambda f=face: self.request_move(Move(f, 1)))
            QShortcut(QKeySequence(f"Shift+{face}"), self,
                      activated=lambda f=face: self.request_move(Move(f, 3)))
            QShortcut(QKeySequence(f"Alt+{face}"), self,
                      activated=lambda f=face: self.request_move(Move(f, 2)))

        for face in _FACE_KEYS:
            face_seq(face)

        QShortcut(QKeySequence("Z"), self, activated=self._do_undo)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._do_undo)
        QShortcut(QKeySequence("S"), self, activated=self._do_scramble)
        QShortcut(QKeySequence("X"), self, activated=self._do_reset)
        QShortcut(QKeySequence("Space"), self,
                  activated=self.solver_panel.btn_play.click)
        QShortcut(QKeySequence("Right"), self, activated=self._do_step)
        QShortcut(QKeySequence("Escape"), self, activated=self._do_stop)
        QShortcut(QKeySequence("1"), self,
                  lambda: self._set_mode("free"))
        QShortcut(QKeySequence("2"), self,
                  lambda: self._set_mode("practice"))
        QShortcut(QKeySequence("3"), self,
                  lambda: self._set_mode("solver"))
        QShortcut(QKeySequence("F1"), self, activated=self._show_about)

    # ---------------------------------------------------------------- wiring

    def _connect(self) -> None:
        # 3D view
        self.view.faceTurnRequested.connect(
            lambda move: self.request_move(move, "user")
        )
        self.view.moveCompleted.connect(self._on_move_completed)
        self.view.queueChanged.connect(lambda _n: self._refresh_undo_state())

        # control panel
        self.control_panel.moveRequested.connect(
            lambda move: self.request_move(move, "user")
        )
        self.control_panel.scrambleRequested.connect(self._do_scramble)
        self.control_panel.undoRequested.connect(self._do_undo)
        self.control_panel.resetRequested.connect(self._do_reset)
        self.control_panel.length_spin.valueChanged.connect(self._on_length_changed)
        self.control_panel.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.control_panel.labels_check.toggled.connect(self._on_labels_toggled)

        # solver panel
        self.solver_panel.solveRequested.connect(self._do_solve)
        self.solver_panel.playPauseToggled.connect(self._toggle_playback)
        self.solver_panel.stepRequested.connect(self._do_step)
        self.solver_panel.stopRequested.connect(self._do_stop)
        self.solver_panel.speedChanged.connect(self._on_playback_speed)

        # mode + topbar
        self.mode_switch.switched_signal().connect(self._set_mode)
        self.btn_panel.toggled.connect(self._toggle_sidebar)
        self.btn_settings.clicked.connect(self._show_settings)
        self.btn_about.clicked.connect(self._show_about)

        # ui timer
        self._ui_timer.timeout.connect(self._on_ui_tick)

    # ------------------------------------------------------------- settings

    def _apply_settings_to_ui(self) -> None:
        speed = float(self.settings.get("animation_speed"))
        self.view.set_speed_multiplier(speed)
        self.control_panel.speed_slider.blockSignals(True)
        self.control_panel.speed_slider.setValue(int(speed * 100))
        self.control_panel.speed_slider.blockSignals(False)
        self.control_panel.speed_value.setText(f"{speed:.1f}×")
        show = bool(self.settings.get("show_face_labels"))
        self.view.set_show_labels(show)
        self.control_panel.labels_check.setChecked(show)
        engine = str(self.settings.get("solver_engine"))
        idx = self.solver_panel.engine_combo.findData(engine)
        if idx >= 0:
            self.solver_panel.engine_combo.setCurrentIndex(idx)
        self.control_panel.length_spin.setValue(int(self.settings.get("scramble_length")))

    def _on_length_changed(self, value: int) -> None:
        self.settings.set("scramble_length", value)

    def _on_speed_changed(self, value: int) -> None:
        self.view.set_speed_multiplier(value / 100.0)
        self.settings.set("animation_speed", value / 100.0)

    def _on_labels_toggled(self, checked: bool) -> None:
        self.view.set_show_labels(checked)
        self.settings.set("show_face_labels", checked)

    def _on_playback_speed(self, value: float) -> None:
        self._playback_speed = value

    # ------------------------------------------------------------ move flow

    def request_move(self, move: Move, source: str = "user",
                     duration_ms: float | None = None) -> None:
        """Entry point for every face turn (buttons, keys, sticker drags)."""
        if source in ("user", "undo") and self._playing:
            self._do_stop()  # user intervention safely stops playback
        if source == "user" and self.view.animator.pending > 48:
            self._set_status("Too many queued moves — slow down a little")
            return
        if source == "undo":
            if self.view.is_animating or not self.user_history:
                return
            last = self.user_history.pop()
            self.view.enqueue_move(last.inverse(), None, "undo")
            return
        if duration_ms is None:
            duration_ms = MOVE_DURATIONS.get(source)
        self.view.enqueue_move(move, duration_ms, source)

    @property
    def solution(self) -> list:
        return self.player.solution

    @property
    def playback_index(self) -> int:
        return self.player.index

    def _on_move_completed(self, move: Move, source: str) -> None:
        """Animation finished: now the logical state updates (single truth)."""
        self.state.apply(move)
        if source == "user":
            self.user_history.append(move)
            self.moves_count += 1
            self.last_move_text = str(move)
            if self._timer_state == "armed":
                self._start_practice_timer()
        elif source == "undo":
            self.moves_count = max(0, self.moves_count - 1)
            self.last_move_text = str(move) + " ↩"
        elif source == "scramble":
            # handled in bulk at scramble time; here just show the move
            self.last_move_text = str(move)
        elif source == "playback":
            self.moves_count += 1
            self.user_history.append(move)
            self.last_move_text = str(move)
            self.player.advance()
            self.solver_panel.set_progress(self.solution, self.player.index)

        solved = self.state.is_solved()
        self._refresh_move_info()
        self.view.resync()

        if source == "playback" and self.player.finished:
            self._playing = False
            self.solver_panel.set_playing(False)
            self.view.set_paused(False)
            self._set_status("Solution playback complete")

        if solved and source == "scramble":
            pass  # astronomically unlikely; ignore
        if solved and source in ("user", "undo"):
            self._on_user_solved()
        if not self.view.is_animating:
            self._set_status(self._idle_status_text())

    def _on_user_solved(self) -> None:
        if self._timer_state == "running":
            self._timer_value = time.perf_counter() - self._timer_start
            self._timer_state = "finished"
            self._final_time = self._timer_value
            record = self.stats.record_solve(
                int(self._timer_value * 1000), self.moves_count, "practice"
            )
            self.stats_panel.refresh()
            self._show_completion(record)
        elif self.mode == "free":
            self._set_status("Cube solved — nice one!")

    # ------------------------------------------------------------- actions

    def _do_scramble(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._do_stop()
        self.view.clear_queue()
        length = int(self.settings.get("scramble_length"))
        moves = random_scramble(length, random.Random())
        self.view.enqueue_many(moves, SCRAMBLE_MOVE_MS, "scramble")
        self.scramble_history.append(moves)
        self.moves_count = 0
        self.user_history.clear()
        self.last_move_text = "--"
        self.info_panel.set_scramble(moves)
        self._reset_practice_timer(armed=True)
        self._set_status(f"Scrambling ({length} moves)…")

    def _do_undo(self) -> None:
        self.request_move(None, "undo")

    def _do_reset(self) -> None:
        self.view.cancel_all()
        self.state.reset()
        self.user_history.clear()
        self.moves_count = 0
        self.last_move_text = "--"
        self.player.clear()
        self._playing = False
        self.solver_panel.clear_solution()
        self.info_panel.set_scramble([])
        self._reset_practice_timer(armed=False)
        self._refresh_all()
        self.view.resync()
        self._set_status("Cube reset to solved state")

    # -- practice timer ---------------------------------------------------------

    def _reset_practice_timer(self, armed: bool) -> None:
        self._timer_state = "armed" if armed else "idle"
        self._timer_value = 0.0
        self._final_time = None
        self.info_panel.set_timer(0.0, running=False)

    def _start_practice_timer(self) -> None:
        self._timer_start = time.perf_counter()
        self._timer_state = "running"
        self._set_status("Timer running — solve the cube!")

    def _on_ui_tick(self) -> None:
        if self._timer_state == "running":
            elapsed = time.perf_counter() - self._timer_start
            self.info_panel.set_timer(elapsed, running=True)
            tps = self.moves_count / elapsed if elapsed > 0.5 else None
            self.info_panel.set_counters(self.moves_count, self.last_move_text, tps)

    # -- solver -------------------------------------------------------------------

    def _do_solve(self, engine: str | None = None) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not engine:
            engine = self.solver_panel.engine_combo.currentData() or "auto"
        try:
            validate(self.state)
        except InvalidCubeError as exc:
            QMessageBox.warning(self, "Cannot solve", f"Invalid cube state:\n{exc}")
            return
        if self.state.is_solved():
            self._set_status("The cube is already solved")
            return
        self._do_stop()
        self.view.clear_queue()
        self.solver_panel.set_solving(True)
        self._set_status("Solving with Kociemba two-phase…"
                         if engine in ("auto", "kociemba") and KOCIEMBA_AVAILABLE
                         else "Solving with layer-by-layer engine…")
        self._worker = _SolverWorker(self.state.clone(), engine)
        self._worker.solved.connect(self._on_solve_done)
        self._worker.errored.connect(self._on_solve_error)
        self._worker.start()

    def _on_solve_done(self, moves: list, engine: str) -> None:
        self.solver_panel.set_solving(False)
        self._worker = None
        # The user may have moved the cube while solving: verify against the
        # *current* state before showing the solution.
        check = self.state.clone()
        check.apply_sequence(moves)
        if not check.is_solved():
            self._set_status("Cube changed during solving — solution discarded")
            return
        self.player.load(moves)
        self.solver_panel.set_solution(self.player.solution, engine_label(engine))
        self._set_status(f"Solution found: {len(moves)} moves ({engine_label(engine)})")

    def _on_solve_error(self, message: str) -> None:
        self.solver_panel.set_solving(False)
        self._worker = None
        QMessageBox.critical(self, "Solver failed", message)
        self._set_status("Solver failed")

    def _toggle_playback(self) -> None:
        if not self.solution:
            return
        if self._playing:
            self.view.set_paused(True)
            self._playing = False
            self.solver_panel.set_playing(False)
            self._set_status("Playback paused")
        else:
            self.view.set_paused(False)
            if self.view.pending_moves == 0:
                remaining = self.player.remaining()
                if not remaining:
                    self.player.restart()
                    remaining = self.player.remaining()
                    self.solver_panel.set_progress(self.solution, 0)
                self.view.enqueue_many(
                    remaining, self._playback_ms(), "playback"
                )
            self._playing = True
            self.solver_panel.set_playing(True)
            self._set_status("Playing solution…")

    def _do_step(self) -> None:
        if not self.solution:
            return
        if self._playing:
            self.view.set_paused(True)
            self._playing = False
            self.solver_panel.set_playing(False)
        if self.view.pending_moves == 0:
            nxt = self.player.next_move()
            if nxt is None:
                self.player.restart()
                nxt = self.player.next_move()
                self.solver_panel.set_progress(self.solution, 0)
            self.view.enqueue_move(nxt, self._playback_ms(), "playback")
            self._set_status("Stepping one move")

    def _do_stop(self) -> None:
        if self._playing or self.view.animator.paused:
            self.view.clear_queue()
            self.view.set_paused(False)
        self._playing = False
        self.solver_panel.set_playing(False)

    def _playback_ms(self) -> float:
        return 260.0 / max(0.2, self._playback_speed)

    # -- modes ---------------------------------------------------------------------

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.mode_switch.set_current(mode)
        if mode == "solver":
            self.tabs.setCurrentWidget(self.solver_panel)
            self._set_status("Solver mode — scramble, then press Solve")
        elif mode == "practice":
            self.tabs.setCurrentWidget(self.control_panel)
            self._set_status(
                "Practice mode — scramble and solve; the timer starts on your first move"
            )
        else:
            self.tabs.setCurrentWidget(self.control_panel)
            self._set_status("Free play — explore the cube")

    # -- panels / dialogs -------------------------------------------------------------

    def _toggle_sidebar(self, visible: bool) -> None:
        self.splitter.widget(1).setVisible(visible)

    def _show_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.stats, self)
        if dlg.exec():
            self._apply_settings_to_ui()
            self.stats_panel.refresh()
            self._set_status("Settings saved")

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _show_completion(self, record: dict) -> None:
        dlg = CompletionDialog(record, self)
        dlg.exec()
        self.info_panel.set_timer(self._timer_value, running=False)
        self._set_status("Practice solve recorded")

    # ---------------------------------------------------------------- status

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _idle_status_text(self) -> str:
        if self.mode == "practice":
            if self._timer_state == "armed":
                return "Scrambled — timer starts on your first move"
            if self._timer_state == "running":
                return "Timer running — solve the cube!"
        return "Ready"

    # --------------------------------------------------------------- refresh

    def _refresh_move_info(self) -> None:
        solved = self.state.is_solved()
        self.info_panel.set_state_badge(solved)
        self.info_panel.refresh_net()
        elapsed = (
            time.perf_counter() - self._timer_start
            if self._timer_state == "running"
            else self._timer_value
        )
        if self._timer_state != "running":
            self.info_panel.set_timer(elapsed or 0.0,
                                      running=self._timer_state == "running")
        tps = None
        if self._timer_state in ("running", "finished") and elapsed > 0.5:
            tps = self.moves_count / elapsed
        self.info_panel.set_counters(self.moves_count, self.last_move_text, tps)
        self._refresh_undo_state()

    def _refresh_undo_state(self) -> None:
        self.control_panel.btn_undo.setEnabled(
            bool(self.user_history) and not self.view.is_animating
        )
        self.control_panel.set_buttons_enabled(not self._playing)

    def _refresh_all(self) -> None:
        self._refresh_move_info()
        self.stats_panel.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._ui_timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(500)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


class SettingsDialog(QDialog):
    """Application settings."""

    def __init__(self, settings: Settings, stats: Statistics, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        self._settings = settings
        self._stats = stats

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        card = Card("Preferences")
        body = card.body()

        row = QHBoxLayout()
        row.addWidget(QLabel("Animation speed"))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(40, 250)
        self.speed.setValue(int(float(settings.get("animation_speed")) * 100))
        self.speed_lbl = QLabel(f"{self.speed.value() / 100:.1f}×")
        self.speed.valueChanged.connect(
            lambda v: self.speed_lbl.setText(f"{v / 100:.1f}×")
        )
        row.addWidget(self.speed, 1)
        row.addWidget(self.speed_lbl)
        body.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Scramble length"))
        self.length = QSpinBox()
        self.length.setRange(1, 40)
        self.length.setValue(int(settings.get("scramble_length")))
        row2.addWidget(self.length)
        row2.addStretch(1)
        body.addLayout(row2)

        self.labels = QCheckBox("Show face letters on center stickers")
        self.labels.setChecked(bool(settings.get("show_face_labels")))
        body.addWidget(self.labels)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Solver engine"))
        self.engine = QComboBox()
        self.engine.addItem("Auto (Kociemba, fallback built-in)", "auto")
        if KOCIEMBA_AVAILABLE:
            self.engine.addItem("Kociemba two-phase only", "kociemba")
        self.engine.addItem("Layer-by-layer only", "lbl")
        idx = self.engine.findData(str(settings.get("solver_engine")))
        if idx >= 0:
            self.engine.setCurrentIndex(idx)
        row3.addWidget(self.engine, 1)
        body.addLayout(row3)
        layout.addWidget(card)

        card2 = Card("Data")
        row4 = QHBoxLayout()
        self.btn_clear = QPushButton("Reset statistics")
        self.btn_clear.setObjectName("danger")
        self.btn_clear.clicked.connect(self._clear_stats)
        row4.addWidget(self.btn_clear)
        row4.addStretch(1)
        note = QLabel("Settings and statistics are stored in the data/ folder.")
        note.setObjectName("hint")
        card2.body().addWidget(note)
        card2.body().addLayout(row4)
        layout.addWidget(card2)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_stats(self) -> None:
        ret = QMessageBox.question(
            self, "Reset statistics",
            "Delete all recorded solves? This cannot be undone.",
        )
        if ret == QMessageBox.Yes:
            self._stats.clear()

    def accept(self) -> None:
        self._settings.set("animation_speed", self.speed.value() / 100.0)
        self._settings.set("scramble_length", self.length.value())
        self._settings.set("show_face_labels", self.labels.isChecked())
        self._settings.set("solver_engine", self.engine.currentData())
        super().accept()


class CompletionDialog(QDialog):
    """Shown when a practice solve is completed."""

    def __init__(self, record: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Solve complete!")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("CUBE SOLVED")
        title.setObjectName("cardTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        from services.statistics import format_time

        big = QLabel(format_time(record["ms"] / 1000.0))
        big.setObjectName("timer")
        big.setAlignment(Qt.AlignCenter)
        layout.addWidget(big)

        grid = QGridLayout()
        grid.setSpacing(8)
        tiles = [
            StatTile("Moves", str(record["moves"])),
            StatTile("TPS", f"{record.get('tps', 0):.2f}"),
        ]
        for i, tile in enumerate(tiles):
            grid.addWidget(tile, 0, i)
        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    """Application information and shortcut reference."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About RUBIK'S LAB")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        head = QHBoxLayout()
        head.addWidget(LogoMark(36))
        box = QVBoxLayout()
        t = QLabel("RUBIK'S LAB")
        t.setObjectName("appTitle")
        s = QLabel(f"Version {APP_VERSION} · 3D cube simulator & solver")
        s.setObjectName("muted")
        box.addWidget(t)
        box.addWidget(s)
        head.addLayout(box)
        layout.addLayout(head)

        body = QLabel(
            "<p>A professional 3D Rubik's Cube simulator: animated face "
            "turns, mouse and keyboard control, WCA-style scrambles, a real "
            "two-phase solver (Kociemba) with a pure-Python layer-by-layer "
            "engine as fallback, practice timing and statistics.</p>"
            "<p><b>Keyboard</b><br>"
            "U / D / L / R / F / B — clockwise quarter turn<br>"
            "Shift + face — counter-clockwise · Alt + face — half turn<br>"
            "S — scramble · Z / Ctrl+Z — undo · X — reset<br>"
            "Space — play/pause solution · → — step · Esc — stop<br>"
            "1 / 2 / 3 — modes · double-click view — reset camera · F1 — this dialog</p>"
        )
        body.setObjectName("muted")
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
