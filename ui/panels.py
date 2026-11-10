"""Side-panel widgets: controls, live info, solver playback, statistics."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.moves import FACES, format_sequence
from services.statistics import Statistics, format_time
from .components import Badge, Card, CubeNet, StatTile, chips_html
from .themes import ACCENT, TEXT_FAINT, TEXT_MUTED


# ---------------------------------------------------------------------------
# Control panel
# ---------------------------------------------------------------------------


class ControlPanel(Card):
    """Move buttons, scramble/undo/reset, session settings."""

    moveRequested = Signal(object)     # Move
    scrambleRequested = Signal()
    undoRequested = Signal()
    resetRequested = Signal()

    def __init__(self, scramble_length: int = 25, parent: QWidget | None = None) -> None:
        super().__init__("Controls", parent)
        self._building = True

        # Move grid: rows per face, columns X / X' / X2.
        grid = QGridLayout()
        grid.setSpacing(6)
        self._move_buttons: dict[str, QPushButton] = {}
        for r, face in enumerate(("U", "D", "L", "R", "F", "B")):
            for c, suffix in enumerate(("", "'", "2")):
                btn = QPushButton(f"{face}{suffix}")
                btn.setObjectName("moveBtn")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.clicked.connect(
                    lambda _=False, f=face, s=suffix: self.moveRequested.emit(
                        _make_move(f, s)
                    )
                )
                self._move_buttons[f"{face}{suffix}"] = btn
                grid.addWidget(btn, r, c)
        self.body().addLayout(grid)

        # Action row.
        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_scramble = QPushButton("Scramble")
        self.btn_scramble.setObjectName("primary")
        self.btn_scramble.setToolTip("Generate a random scramble (S)")
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setToolTip("Undo your last move (Z)")
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("danger")
        self.btn_reset.setToolTip("Return the cube to solved (X)")
        for b in (self.btn_scramble, self.btn_undo, self.btn_reset):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        self.btn_scramble.clicked.connect(self.scrambleRequested.emit)
        self.btn_undo.clicked.connect(self.undoRequested.emit)
        self.btn_reset.clicked.connect(self.resetRequested.emit)
        self.body().addLayout(row)

        # Session settings.
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Scramble length"))
        self.length_spin = QSpinBox()
        self.length_spin.setRange(1, 40)
        self.length_spin.setValue(scramble_length)
        row2.addWidget(self.length_spin)
        row2.addStretch(1)
        self.body().addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Animation"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(40, 250)          # percent
        self.speed_slider.setValue(100)
        self.speed_slider.setToolTip("Animation speed")
        row3.addWidget(self.speed_slider, 1)
        self.speed_value = QLabel("1.0×")
        row3.addWidget(self.speed_value)
        self.body().addLayout(row3)

        self.labels_check = QCheckBox("Show face letters on centers")
        self.labels_check.setChecked(True)
        self.body().addWidget(self.labels_check)

        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value.setText(f"{v / 100:.1f}×")
        )
        self._building = False

    def set_buttons_enabled(self, enabled: bool) -> None:
        # NOTE: btn_undo is deliberately NOT managed here; its state is
        # owned by MainWindow._refresh_undo_state (history-dependent).
        for btn in self._move_buttons.values():
            btn.setEnabled(enabled)
        self.btn_scramble.setEnabled(enabled)


def _make_move(face: str, suffix: str):
    from core.moves import Move

    return Move(face, {"": 1, "'": 3, "2": 2}[suffix])


# ---------------------------------------------------------------------------
# Info panel
# ---------------------------------------------------------------------------


class InfoPanel(Card):
    """Timer, counters, state badge, scramble readout and the 2D net."""

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__("Session", parent)
        self._state = state

        self.timer_label = QLabel("00:00.00")
        self.timer_label.setObjectName("timer")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.body().addWidget(self.timer_label)

        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_moves = StatTile("Moves", "0")
        self.tile_last = StatTile("Last move", "--")
        self.tile_tps = StatTile("TPS", "--")
        tiles.addWidget(self.tile_moves)
        tiles.addWidget(self.tile_last)
        tiles.addWidget(self.tile_tps)
        self.body().addLayout(tiles)

        self.state_badge = Badge("Solved", "ok")
        self.body().addWidget(self.state_badge)

        self.scramble_title = QLabel("SCRAMBLE")
        self.scramble_title.setObjectName("cardTitle")
        self.scramble_title.hide()
        self.body().addWidget(self.scramble_title)
        self.scramble_label = QLabel("")
        self.scramble_label.setObjectName("solutionText")
        self.scramble_label.setWordWrap(True)
        self.scramble_label.setTextFormat(Qt.RichText)
        self.scramble_label.hide()
        self.body().addWidget(self.scramble_label)

        self.net = CubeNet(state)
        self.body().addWidget(self.net, 0, Qt.AlignHCenter)

    # -- updates ------------------------------------------------------------------

    def set_timer(self, seconds: float | None, running: bool) -> None:
        self.timer_label.setText(
            format_time(seconds) if seconds is not None else "00:00.00"
        )
        self.timer_label.setObjectName("timerRunning" if running else "timer")
        # force stylesheet re-evaluation
        self.timer_label.style().unpolish(self.timer_label)
        self.timer_label.style().polish(self.timer_label)

    def set_counters(self, moves: int, last_move: str, tps: float | None) -> None:
        self.tile_moves.set_value(str(moves))
        self.tile_last.set_value(last_move or "--")
        self.tile_tps.set_value(f"{tps:.2f}" if tps else "--")

    def set_state_badge(self, solved: bool) -> None:
        if solved:
            self.state_badge.set_text("Solved ✓", "ok")
        else:
            self.state_badge.set_text("Scrambled", "warn")

    def set_scramble(self, moves) -> None:
        if moves:
            self.scramble_title.show()
            self.scramble_label.show()
            self.scramble_label.setText(chips_html(moves, -1, chip_px=12))
        else:
            self.scramble_title.hide()
            self.scramble_label.hide()

    def refresh_net(self) -> None:
        self.net.update()


# ---------------------------------------------------------------------------
# Solver panel
# ---------------------------------------------------------------------------


class SolverPanel(Card):
    """Solve request, solution display, playback controls and progress."""

    solveRequested = Signal(str)           # engine
    playPauseToggled = Signal()
    stepRequested = Signal()
    stopRequested = Signal()
    speedChanged = Signal(float)

    def __init__(self, engine_options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__("Solver", parent)

        row = QHBoxLayout()
        self.btn_solve = QPushButton("Solve cube")
        self.btn_solve.setObjectName("primary")
        self.btn_solve.setToolTip("Compute a solution for the current state")
        self.btn_solve.clicked.connect(
            lambda: self.solveRequested.emit(self.engine_combo.currentData())
        )
        self.engine_combo = QComboBox()
        for key, label in engine_options:
            self.engine_combo.addItem(label, key)
        self.engine_combo.setCurrentIndex(0)
        row.addWidget(self.btn_solve, 1)
        row.addWidget(self.engine_combo)
        self.body().addLayout(row)

        self.engine_note = QLabel("")
        self.engine_note.setObjectName("hint")
        self.engine_note.setWordWrap(True)
        self.body().addWidget(self.engine_note)

        self.solution_title = QLabel("SOLUTION")
        self.solution_title.setObjectName("cardTitle")
        self.solution_title.hide()
        self.body().addWidget(self.solution_title)
        self.solution_label = QLabel("")
        self.solution_label.setObjectName("solutionText")
        self.solution_label.setWordWrap(True)
        self.solution_label.setTextFormat(Qt.RichText)
        self.solution_label.hide()
        self.body().addWidget(self.solution_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()
        self.body().addWidget(self.progress)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("hint")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.hide()
        self.body().addWidget(self.progress_label)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.btn_play = QPushButton("Play")
        self.btn_step = QPushButton("Step")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("ghost")
        for b in (self.btn_play, self.btn_step, self.btn_stop):
            b.setCursor(Qt.PointingHandCursor)
            row2.addWidget(b)
        self.body().addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Playback"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(40, 260)
        self.speed_slider.setValue(100)
        row3.addWidget(self.speed_slider, 1)
        self.speed_value = QLabel("1.0×")
        row3.addWidget(self.speed_value)
        self.body().addLayout(row3)
        self.speed_slider.valueChanged.connect(
            lambda v: (self.speed_value.setText(f"{v / 100:.1f}×"),
                       self.speedChanged.emit(v / 100.0))
        )

        self.btn_play.clicked.connect(self.playPauseToggled.emit)
        self.btn_step.clicked.connect(self.stepRequested.emit)
        self.btn_stop.clicked.connect(self.stopRequested.emit)

        self._has_solution = False
        self._playing = False
        self._set_controls()

    # -- state -----------------------------------------------------------------------

    def set_engine_note(self, text: str) -> None:
        self.engine_note.setText(text)

    def set_solving(self, busy: bool) -> None:
        self.btn_solve.setEnabled(not busy)
        self.btn_solve.setText("Solving…" if busy else "Solve cube")

    def set_solution(self, moves, engine_label: str) -> None:
        self._has_solution = bool(moves)
        self.solution_title.show()
        self.solution_label.show()
        self.progress.show()
        self.progress_label.show()
        self.progress.setRange(0, max(1, len(moves)))
        self.progress.setValue(0)
        self._update_label(moves, -1)
        self.progress_label.setText(
            f"{len(moves)} moves · engine: {engine_label}"
        )
        self._playing = False
        self.btn_play.setText("Play")
        self._set_controls()

    def clear_solution(self) -> None:
        self._has_solution = False
        self.solution_title.hide()
        self.solution_label.hide()
        self.progress.hide()
        self.progress_label.hide()
        self._playing = False
        self.btn_play.setText("Play")
        self._set_controls()

    def set_progress(self, moves, index: int) -> None:
        """index = number of moves already executed."""
        self.progress.setValue(index)
        self._update_label(moves, index - 1 if index > 0 else -1)
        self.progress_label.setText(
            f"Move {min(index + 1, len(moves))} / {len(moves)}"
            if index < len(moves)
            else f"Complete · {len(moves)} moves"
        )

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self.btn_play.setText("Pause" if playing else "Play")
        self._set_controls()

    def set_enabled(self, enabled: bool) -> None:
        self.btn_solve.setEnabled(enabled)
        self.engine_combo.setEnabled(enabled)
        self._enabled = enabled
        self._set_controls()

    def _update_label(self, moves, current: int) -> None:
        self.solution_label.setText(chips_html(moves, current, chip_px=13))

    def _set_controls(self) -> None:
        playback_on = self._has_solution
        self.btn_play.setEnabled(playback_on)
        self.btn_step.setEnabled(playback_on)
        self.btn_stop.setEnabled(playback_on)


# ---------------------------------------------------------------------------
# Stats panel
# ---------------------------------------------------------------------------


class StatsPanel(Card):
    """Aggregated practice statistics and the recent solve list."""

    def __init__(self, stats: Statistics, parent: QWidget | None = None) -> None:
        super().__init__("Statistics", parent)
        self._stats = stats

        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_count = StatTile("Solves", "0")
        self.tile_best = StatTile("Best", "--")
        self.tile_ao5 = StatTile("Ao5", "--")
        self.tile_ao12 = StatTile("Ao12", "--")
        for t in (self.tile_count, self.tile_best, self.tile_ao5, self.tile_ao12):
            tiles.addWidget(t)
        self.body().addLayout(tiles)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Time", "Moves", "TPS"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 60)
        self.table.setMinimumHeight(190)
        self.body().addWidget(self.table, 1)

        self.note = QLabel("Complete a Practice solve to record statistics.")
        self.note.setObjectName("hint")
        self.note.setWordWrap(True)
        self.body().addWidget(self.note)

    # -- updates ---------------------------------------------------------------------

    def refresh(self) -> None:
        s = self._stats.summary()
        self.tile_count.set_value(str(s["count"]))
        self.tile_best.set_value(format_time(s["best"]))
        self.tile_ao5.set_value(format_time(s["ao5"]))
        self.tile_ao12.set_value(format_time(s["ao12"]))

        recent = self._stats.recent(12)
        self.table.setRowCount(len(recent))
        total = self._stats.count()
        for row, rec in enumerate(recent):
            idx = total - row
            values = (
                str(idx),
                format_time(rec["ms"] / 1000.0),
                str(rec["moves"]),
                f"{rec.get('tps', 0):.2f}",
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(row, col, item)

        self.note.setVisible(self._stats.count() == 0)
