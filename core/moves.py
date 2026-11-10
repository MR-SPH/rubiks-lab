"""Face-turn definitions, integer rotation matrices and notation helpers.

This module is intentionally dependency-free (pure Python, integer math only):
the logical cube state must be exact, never floating point.

Conventions
-----------
* Coordinate system: x points right (R face), y points up (U face),
  z points towards the viewer (F face).
* A face turn "X" (clockwise) is defined as a *clockwise* rotation of the
  face when looking at that face from outside the cube.  In right-handed
  terms this is a rotation by -90 degrees about the face's outward normal.
* ``Move.turns`` is the number of clockwise quarter turns: 1 = X, 2 = X2,
  3 = X'.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Face constants
# ---------------------------------------------------------------------------

#: Faces in standard Kociemba facelet order (used to build solver strings).
FACES: tuple[str, ...] = ("U", "R", "F", "D", "L", "B")

#: Rotation axis index of each face (0 = x, 1 = y, 2 = z).
FACE_AXIS: dict[str, int] = {"U": 1, "D": 1, "F": 2, "B": 2, "R": 0, "L": 0}

#: Sign of each face's outward normal along its axis.
FACE_SIGN: dict[str, int] = {"U": 1, "D": -1, "F": 1, "B": -1, "R": 1, "L": -1}

#: Outward normal vector of each face.
FACE_NORMAL: dict[str, tuple[int, int, int]] = {
    "U": (0, 1, 0),
    "D": (0, -1, 0),
    "F": (0, 0, 1),
    "B": (0, 0, -1),
    "R": (1, 0, 0),
    "L": (-1, 0, 0),
}

#: Ring order used for algorithm face-substitution (F -> R -> B -> L).
_SIDE_RING: tuple[str, ...] = ("F", "R", "B", "L")
_SIDE_INDEX: dict[str, int] = {f: i for i, f in enumerate(_SIDE_RING)}


# ---------------------------------------------------------------------------
# Move dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Move:
    """A single face turn.

    ``turns`` is the number of *clockwise* quarter turns: 1 (X), 2 (X2), 3 (X').
    """

    face: str
    turns: int = 1

    def __post_init__(self) -> None:
        if self.face not in FACE_AXIS:
            raise ValueError(f"Unknown face {self.face!r}")
        if self.turns not in (1, 2, 3):
            raise ValueError(f"turns must be 1, 2 or 3, got {self.turns}")

    # -- helpers ------------------------------------------------------------

    @property
    def axis(self) -> int:
        """Rotation axis index (0 = x, 1 = y, 2 = z)."""
        return FACE_AXIS[self.face]

    @property
    def layer(self) -> int:
        """Coordinate along the axis that identifies the turning layer."""
        return FACE_SIGN[self.face]

    def inverse(self) -> "Move":
        """The move that undoes this one (X -> X', X2 -> X2)."""
        return Move(self.face, 4 - self.turns)

    def shifted(self, k: int) -> "Move":
        """Same move with the side face rotated ``k`` steps along F->R->B->L.

        U and D faces are unaffected (they are not part of the side ring).
        Used to transpose generic algorithms around the cube.
        """
        return Move(shift_face(self.face, k), self.turns)

    def __str__(self) -> str:  # noqa: D105
        return move_to_str(self)


def move_to_str(move: Move) -> str:
    """Standard notation: ``R``, ``R'``, ``R2``."""
    if move.turns == 1:
        return move.face
    if move.turns == 2:
        return f"{move.face}2"
    return f"{move.face}'"


def shift_face(face: str, k: int) -> str:
    """Rotate a side face ``k`` steps along the F -> R -> B -> L ring."""
    if face in _SIDE_INDEX:
        return _SIDE_RING[(_SIDE_INDEX[face] + k) % 4]
    return face  # U / D


# ---------------------------------------------------------------------------
# Integer rotation matrices (3x3, row-major tuples)
# ---------------------------------------------------------------------------

Matrix3 = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]

IDENTITY3: Matrix3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

# Base +90-degree right-handed rotation about each positive axis.
_QUARTER: dict[int, Matrix3] = {
    # +90 deg about x: y -> z, z -> -y
    0: ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    # +90 deg about y: z -> x, x -> -z
    1: ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    # +90 deg about z: x -> y, y -> -x
    2: ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}


def mat_mul(a: Matrix3, b: Matrix3) -> Matrix3:
    """Multiply two 3x3 integer matrices (``a`` then ``b`` applied as a*b)."""
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def mat_vec(m: Matrix3, v: tuple[int, int, int]) -> tuple[int, int, int]:
    """Apply a 3x3 integer matrix to a vector."""
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def rotation_quarter(axis: int, k: int) -> Matrix3:
    """``k`` right-handed +90-degree rotations about the positive ``axis``."""
    k %= 4
    result: Matrix3 = IDENTITY3
    base = _QUARTER[axis]
    for _ in range(k):
        result = mat_mul(base, result)
    return result


def move_matrix(move: Move) -> Matrix3:
    """Exact integer rotation matrix of a face turn.

    A clockwise quarter turn viewed from outside the face equals a
    right-handed rotation by -90 degrees about the face's outward normal,
    i.e. ``(4 - turns)`` +90-degree rotations about the outward *axis
    direction* (accounting for the sign of the normal).
    """
    k = (-move.turns * FACE_SIGN[move.face]) % 4
    return rotation_quarter(move.axis, k)


# ---------------------------------------------------------------------------
# Notation parsing / formatting
# ---------------------------------------------------------------------------


def parse_sequence(text: str) -> list[Move]:
    """Parse standard notation like ``"R U' F2"`` into moves.

    Accepted tokens: ``X``, ``X'``, ``X2`` (optionally ``X2'``) for
    X in U/D/F/B/R/L.  Whitespace separated.  Raises ValueError on garbage.
    Normalizes common typographic quotes/primes (’, ′, ‘).
    """
    normalized = (
        text.replace(",", " ")
        .replace("\u2019", "'")
        .replace("\u2032", "'")
        .replace("\u2018", "'")
        .replace("\u2035", "'")
        .replace("`", "'")
    )
    moves: list[Move] = []
    for token in normalized.split():
        if not token:
            continue
        face = token[0].upper()
        rest = token[1:]
        if face not in FACE_AXIS:
            raise ValueError(f"Unknown face in token {token!r}")
        if rest in ("",):
            moves.append(Move(face, 1))
        elif rest == "'":
            moves.append(Move(face, 3))
        elif rest == "2":
            moves.append(Move(face, 2))
        elif rest == "2'":
            moves.append(Move(face, 2))
        else:
            raise ValueError(f"Invalid move token {token!r}")
    return moves


def format_sequence(moves: list[Move]) -> str:
    """Format moves as standard notation, space separated."""
    return " ".join(move_to_str(m) for m in moves)


def invert_sequence(moves: list[Move]) -> list[Move]:
    """Moves that undo ``moves`` (reverse order, each inverted)."""
    return [m.inverse() for m in reversed(moves)]


def simplify(moves: list[Move]) -> list[Move]:
    """Merge/cancel adjacent turns of the same face (U U -> U2, R R' -> ...).

    Only *adjacent* moves are merged; the sequence is never reordered.
    Runs to a fixed point so chains like ``R R R R`` collapse to ``[]``.
    """
    out: list[Move] = []
    for move in moves:
        if out and out[-1].face == move.face:
            total = (out[-1].turns + move.turns) % 4
            out.pop()
            if total != 0:
                out.append(Move(move.face, total))
        else:
            out.append(move)
    # A pass may create new adjacencies (e.g. R R -> R2 next to R2); repeat.
    if len(out) != len(moves):
        return simplify(out)
    return out
