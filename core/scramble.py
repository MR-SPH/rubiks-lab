"""Random scramble generation (WCA-style constraints)."""

from __future__ import annotations

import random

from .moves import Move, FACE_AXIS, FACES, invert_sequence

#: All quarter/half turn variants, in a fixed display order.
_TURN_ORDER = (1, 3, 2)  # X, X', X2


def random_scramble(length: int = 25, rng: random.Random | None = None) -> list[Move]:
    """Generate a random scramble of ``length`` moves.

    Constraints (mirroring WCA scramble rules):
    * no two consecutive moves on the same face;
    * no ``A B A`` pattern where A and B are faces of the same axis
      (e.g. ``R L R``), which is always a wasted move.

    The generator is deterministic for a given seeded ``rng``.
    """
    if length < 1:
        raise ValueError("Scramble length must be >= 1")
    rng = rng or random.Random()
    moves: list[Move] = []
    while len(moves) < length:
        face = rng.choice(FACES)
        if moves:
            if face == moves[-1].face:
                continue
            if len(moves) >= 2:
                prev2 = moves[-2]
                if (
                    FACE_AXIS[face] == FACE_AXIS[prev2.face]
                    and FACE_AXIS[face] == FACE_AXIS[moves[-1].face]
                ):
                    continue
        moves.append(Move(face, rng.choice(_TURN_ORDER)))
    return moves


def inverse_scramble(moves: list[Move]) -> list[Move]:
    """Moves that undo a scramble (convenience wrapper)."""
    return invert_sequence(moves)
