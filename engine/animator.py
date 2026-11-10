"""Animation queue for face turns.

Contract (this is what keeps visuals and logic synchronised):

* The queue plays moves one at a time; moves never overlap.
* While a move animates, the *logical* state is still the pre-move state;
  the renderer applies a rotation overlay to the affected cubies only.
* When the animation finishes, the owner of the logical state is notified
  (``on_complete`` callback) and applies the move; only after that does
  the queue start the next animation.  The overlay is always an exact
  rotation and ends exactly at the 90/180/270 degree position, so there
  is no accumulated floating-point drift: every frame the renderer
  combines the *integer* logical transform with at most one clean overlay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.moves import Move, FACE_AXIS, FACE_SIGN


@dataclass
class ActiveAnimation:
    """State of the move currently being animated."""

    move: Move
    axis: int                 # rotation axis index (0=x, 1=y, 2=z)
    duration_ms: float        # total duration
    elapsed_ms: float = 0.0
    source: str = "user"

    @property
    def total_angle(self) -> float:
        """Final angle in radians about the +axis (right-handed)."""
        return -math.pi / 2 * self.move.turns * FACE_SIGN[self.move.face]

    @property
    def angle(self) -> float:
        """Current overlay angle (eased)."""
        t = min(1.0, self.elapsed_ms / max(1.0, self.duration_ms))
        return self.total_angle * ease_in_out(t)

    @property
    def done(self) -> bool:
        return self.elapsed_ms >= self.duration_ms


def ease_in_out(t: float) -> float:
    """Cubic ease-in-out; smooth starts and stops."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


class AnimationQueue:
    """Serial FIFO queue of animated face turns."""

    def __init__(self) -> None:
        self._queue: list[tuple[Move, float, str]] = []
        self.active: Optional[ActiveAnimation] = None
        self._paused = False
        self.on_complete: Optional[Callable[[Move, str], None]] = None
        self.on_queue_changed: Optional[Callable[[], None]] = None

    # -- public API ------------------------------------------------------------

    def enqueue(self, move: Move, duration_ms: float, source: str = "user") -> None:
        """Queue a move; starts immediately if the queue is idle."""
        self._queue.append((move, float(duration_ms), source))
        self._notify_queue()
        self._maybe_start_next()

    def enqueue_many(
        self, moves, duration_ms: float, source: str = "user"
    ) -> None:
        for move in moves:
            self._queue.append((move, float(duration_ms), source))
        self._notify_queue()
        self._maybe_start_next()

    def clear(self) -> int:
        """Drop every pending (not yet started) move. Returns how many."""
        n = len(self._queue)
        self._queue.clear()
        self._notify_queue()
        return n

    def cancel_all(self) -> None:
        """Drop the queue AND the active animation without completing it.

        Used by Reset: the logical state is about to be replaced wholesale,
        so the in-flight move must not fire its completion callback.
        """
        self._queue.clear()
        self.active = None
        self._paused = False
        self._notify_queue()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def is_busy(self) -> bool:
        return self.active is not None or bool(self._queue)

    @property
    def pending(self) -> int:
        """Moves waiting (including the active one)."""
        return len(self._queue) + (1 if self.active else 0)

    # -- frame update ------------------------------------------------------------

    def tick(self, dt_ms: float) -> None:
        """Advance the animation by ``dt_ms``; complete at most one move."""
        if self.active is None:
            self._maybe_start_next()
            if self.active is None:
                return
        self.active.elapsed_ms += dt_ms
        if self.active.done:
            finished = self.active
            self.active = None
            if self.on_complete is not None:
                # The owner applies the logical move here, then (because the
                # callback is synchronous) we may start the next animation
                # against the freshly-synced visuals.
                self.on_complete(finished.move, finished.source)
            self._maybe_start_next()

    # -- internals -----------------------------------------------------------------

    def _maybe_start_next(self) -> None:
        if self.active is not None or self._paused or not self._queue:
            return
        move, duration, source = self._queue.pop(0)
        self.active = ActiveAnimation(
            move=move,
            axis=FACE_AXIS[move.face],
            duration_ms=duration,
            source=source,
        )
        self._notify_queue()

    def _notify_queue(self) -> None:
        if self.on_queue_changed is not None:
            self.on_queue_changed()
