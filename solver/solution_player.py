"""Solution playback state machine.

A tiny, UI-independent controller that tracks progress through a computed
solution.  The MainWindow wires it to the animation queue: moves are
executed by the queue, and every completed playback move is reported back
here, which keeps playback correct even when moves are paused, stepped
or interrupted.

This module has no Qt dependency, so it is fully unit-testable.
"""

from __future__ import annotations

from core.moves import Move


class SolutionPlayer:
    """Index/progress tracking for playing back a solution sequence."""

    def __init__(self) -> None:
        self._solution: list[Move] = []
        self.index = 0            # number of moves already executed

    # -- lifecycle -------------------------------------------------------------

    def load(self, solution: list[Move]) -> None:
        """Start a new solution from the beginning."""
        self._solution = list(solution)
        self.index = 0

    def clear(self) -> None:
        self._solution = []
        self.index = 0

    def restart(self) -> None:
        self.index = 0

    # -- queries ---------------------------------------------------------------

    @property
    def solution(self) -> list[Move]:
        return list(self._solution)

    @property
    def finished(self) -> bool:
        return bool(self._solution) and self.index >= len(self._solution)

    def remaining(self) -> list[Move]:
        """Moves not yet executed."""
        return self._solution[self.index:]

    def next_move(self) -> Move | None:
        """The next move to execute (or None when finished)."""
        if self.index < len(self._solution):
            return self._solution[self.index]
        return None

    # -- progress ----------------------------------------------------------------

    def advance(self) -> Move:
        """Record that the next move has been executed; return it."""
        move = self._solution[self.index]
        self.index += 1
        return move

    def progress_text(self) -> str:
        if not self._solution:
            return ""
        if self.index >= len(self._solution):
            return f"Complete · {len(self._solution)} moves"
        return f"Move {self.index + 1} / {len(self._solution)}"
