"""Logical 3x3x3 Rubik's Cube state.

Design rules
------------
* The cube is represented exactly: 26 cubies, each with an integer grid
  position (x, y, z in {-1, 0, 1}) and an integer 3x3 orientation matrix.
  No floating point is ever involved in the logical state.
* Sticker colors are the home face letters ("U", "D", "F", "B", "R", "L").
* Applying a move permutes positions and rotates orientation matrices with
  exact integer arithmetic.  The facelet projection (used by the solver and
  the validator) is derived on demand from the cubie data.

Coordinate system: x -> R, y -> U, z -> F.
"""

from __future__ import annotations

from itertools import product

from .moves import (
    IDENTITY3,
    Matrix3,
    Move,
    FACE_NORMAL,
    mat_mul,
    mat_vec,
    move_matrix,
)

#: All 26 cubie grid positions (the invisible core (0,0,0) is excluded).
CUBIE_POSITIONS: list[tuple[int, int, int]] = [
    p for p in product((-1, 0, 1), repeat=3) if p != (0, 0, 0)
]


class Cubie:
    """One cubie: home position, current position, orientation, stickers.

    ``stickers`` maps a *local* normal direction (fixed for the cubie's
    lifetime) to a color (the home face letter).  The sticker's *world*
    normal is ``ori . local_normal``.
    """

    __slots__ = ("home", "pos", "ori", "stickers")

    def __init__(
        self,
        home: tuple[int, int, int],
        stickers: tuple[tuple[tuple[int, int, int], str], ...],
    ) -> None:
        self.home = home
        self.pos = home
        self.ori: Matrix3 = IDENTITY3
        self.stickers = stickers

    def clone(self) -> "Cubie":
        c = Cubie(self.home, self.stickers)
        c.pos = self.pos
        c.ori = self.ori
        return c

    def world_normal(self, local_normal: tuple[int, int, int]) -> tuple[int, int, int]:
        """Where a sticker with the given local normal currently faces."""
        return mat_vec(self.ori, local_normal)

    def sticker_facing(self, direction: tuple[int, int, int]) -> str | None:
        """Color of the sticker currently facing ``direction`` (or None)."""
        for normal, color in self.stickers:
            if mat_vec(self.ori, normal) == direction:
                return color
        return None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Cubie(home={self.home}, pos={self.pos})"


class CubeState:
    """The logical cube: a mapping from grid position to cubie.

    This class is the single source of truth for the whole application.
    The renderer only ever *reads* snapshots from it; moves are applied
    here and the visuals re-sync from it after every animation step.
    """

    __slots__ = ("_by_pos",)

    def __init__(self) -> None:
        self._by_pos: dict[tuple[int, int, int], Cubie] = {}
        for pos in CUBIE_POSITIONS:
            stickers = tuple(
                (FACE_NORMAL[face], face)
                for face in ("U", "D", "F", "B", "R", "L")
                if sum(a * b for a, b in zip(FACE_NORMAL[face], pos)) == 1
            )
            self._by_pos[pos] = Cubie(pos, stickers)

    # -- basic protocol -----------------------------------------------------

    def clone(self) -> "CubeState":
        other = CubeState.__new__(CubeState)
        other._by_pos = {pos: cubie.clone() for pos, cubie in self._by_pos.items()}
        return other

    def cubie_at(self, pos: tuple[int, int, int]) -> Cubie | None:
        """The cubie currently occupying grid position ``pos``."""
        return self._by_pos.get(pos)

    @property
    def cubies(self) -> dict[tuple[int, int, int], Cubie]:
        """Position -> cubie mapping (read-only view)."""
        return self._by_pos

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CubeState):
            return NotImplemented
        return self.semantic_key() == other.semantic_key()

    def semantic_key(self) -> tuple:
        """State hash key based on piece placement and sticker colors.

        Deliberately ignores the spin of center cubies around their own
        axis (visually and functionally irrelevant).
        """
        items = []
        for pos in CUBIE_POSITIONS:
            c = self._by_pos[pos]
            stickers = tuple(
                sorted((c.world_normal(n), col) for n, col in c.stickers)
            )
            items.append((c.home, pos, stickers))
        return tuple(items)

    def __hash__(self) -> int:  # pragma: no cover - rarely used
        return hash(self.semantic_key())

    # -- moves ---------------------------------------------------------------

    def apply(self, move: Move) -> None:
        """Apply a single face turn, in place, with exact integer math."""
        m = move_matrix(move)
        axis, layer = move.axis, move.layer
        moved: dict[tuple[int, int, int], Cubie] = {}
        for pos, cubie in self._by_pos.items():
            if pos[axis] == layer:
                new_pos = mat_vec(m, pos)
                cubie.pos = new_pos
                cubie.ori = mat_mul(m, cubie.ori)
                moved[new_pos] = cubie
        # Only the moved cubies change slots; overwrite their new positions.
        for new_pos, cubie in moved.items():
            self._by_pos[new_pos] = cubie

    def apply_sequence(self, moves) -> None:
        for move in moves:
            self.apply(move)

    def reset(self) -> None:
        """Return every cubie to its home position and orientation."""
        for cubie in self._by_pos.values():
            cubie.pos = cubie.home
            cubie.ori = IDENTITY3
        # Rebuild the position map: the cubies themselves are the truth.
        self._by_pos = {cubie.pos: cubie for cubie in self._by_pos.values()}

    # -- queries -------------------------------------------------------------

    def is_solved(self) -> bool:
        """True when every face shows a single color."""
        for face, normal in FACE_NORMAL.items():
            colors = set()
            for pos in CUBIE_POSITIONS:
                if sum(a * b for a, b in zip(normal, pos)) != 1:
                    continue
                cubie = self._by_pos[pos]
                colors.add(cubie.sticker_facing(normal))
            if len(colors) != 1:
                return False
        return True

    def facelets(self) -> dict[str, list[str]]:
        """54 facelet colors in Kociemba layout, per face, reading order.

        Face reading order matches the standard two-phase solver layout
        (each face read from its own outside view; see FACELET_POSITIONS).
        """
        out: dict[str, list[str]] = {}
        for face, positions in FACELET_POSITIONS.items():
            normal = FACE_NORMAL[face]
            row = []
            for pos in positions:
                cubie = self._by_pos[pos]
                color = cubie.sticker_facing(normal)
                if color is None:  # pragma: no cover - impossible for legal moves
                    raise RuntimeError(f"No sticker facing {face} at {pos}")
                row.append(color)
            out[face] = row
        return out

    def facelet_string(self) -> str:
        """Kociemba solver string: URFDLB order, 54 face letters."""
        f = self.facelets()
        return "".join("".join(f[face]) for face in ("U", "R", "F", "D", "L", "B"))

    def last_move_restored(self) -> bool:  # pragma: no cover - helper, unused
        return self.is_solved()


# ---------------------------------------------------------------------------
# Kociemba facelet layout
# ---------------------------------------------------------------------------
# Each face is listed as its 9 grid positions in the standard reading order:
#   U: viewed from above, B at top      rows run z=-1..+1, x=-1..+1
#   R: viewed from the right            rows y=+1..-1, cols z=+1..-1
#   F: viewed from the front            rows y=+1..-1, cols x=-1..+1
#   D: viewed from below, F at top      rows run z=+1..-1, x=-1..+1
#   L: viewed from the left             rows y=+1..-1, cols z=-1..+1
#   B: viewed from the back             rows y=+1..-1, cols x=+1..-1

FACELET_POSITIONS: dict[str, list[tuple[int, int, int]]] = {
    "U": [
        (-1, 1, -1), (0, 1, -1), (1, 1, -1),
        (-1, 1, 0), (0, 1, 0), (1, 1, 0),
        (-1, 1, 1), (0, 1, 1), (1, 1, 1),
    ],
    "R": [
        (1, 1, 1), (1, 1, 0), (1, 1, -1),
        (1, 0, 1), (1, 0, 0), (1, 0, -1),
        (1, -1, 1), (1, -1, 0), (1, -1, -1),
    ],
    "F": [
        (-1, 1, 1), (0, 1, 1), (1, 1, 1),
        (-1, 0, 1), (0, 0, 1), (1, 0, 1),
        (-1, -1, 1), (0, -1, 1), (1, -1, 1),
    ],
    "D": [
        (-1, -1, 1), (0, -1, 1), (1, -1, 1),
        (-1, -1, 0), (0, -1, 0), (1, -1, 0),
        (-1, -1, -1), (0, -1, -1), (1, -1, -1),
    ],
    "L": [
        (-1, 1, -1), (-1, 1, 0), (-1, 1, 1),
        (-1, 0, -1), (-1, 0, 0), (-1, 0, 1),
        (-1, -1, -1), (-1, -1, 0), (-1, -1, 1),
    ],
    "B": [
        (1, 1, -1), (0, 1, -1), (-1, 1, -1),
        (1, 0, -1), (0, 0, -1), (-1, 0, -1),
        (1, -1, -1), (0, -1, -1), (-1, -1, -1),
    ],
}
