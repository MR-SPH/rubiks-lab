"""Cube state validation: can this state occur on a real, legal cube?

Implements the four classic invariants (the same ones the two-phase solver
checks, formulated directly on the cubie representation):

1. Every color appears exactly 9 times.
2. Every edge and corner piece exists exactly once (no swapped stickers,
   no mirrored pieces).
3. Edge flip parity is even (sum of flips == 0 mod 2).
4. Corner twist sum == 0 mod 3, and edge/corner permutation parities match.
"""

from __future__ import annotations

from .cube import CubeState

EDGES: tuple[tuple[str, str], ...] = (
    ("U", "R"), ("U", "F"), ("U", "L"), ("U", "B"),
    ("D", "R"), ("D", "F"), ("D", "L"), ("D", "B"),
    ("F", "R"), ("F", "L"), ("B", "R"), ("B", "L"),
)

# Home grid positions for the canonical edge ordering above.
EDGE_HOME: tuple[tuple[int, int, int], ...] = (
    (1, 1, 0), (0, 1, 1), (-1, 1, 0), (0, 1, -1),
    (1, -1, 0), (0, -1, 1), (-1, -1, 0), (0, -1, -1),
    (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
)

CORNER_HOME: tuple[tuple[int, int, int], ...] = (
    (1, 1, 1), (-1, 1, 1), (-1, 1, -1), (1, 1, -1),
    (1, -1, 1), (-1, -1, 1), (-1, -1, -1), (1, -1, -1),
)

# Kociemba's per-slot cyclic face triples (cornerFacelet table mapped to
# grid directions).  For a corner sitting in a slot, the index of the slot
# direction its U/D sticker faces IS its twist value (0/1/2), and the cyclic
# color sequence starting at the U/D color identifies the piece.  These
# triples are chosen with consistent chirality, which is exactly what makes
# the "sum of twists == 0 mod 3" invariant hold for legal moves.
CORNER_SLOT_DIRS: dict[tuple[int, int, int], tuple[tuple[int, int, int], ...]] = {
    (1, 1, 1): ((0, 1, 0), (1, 0, 0), (0, 0, 1)),      # U, R, F
    (-1, 1, 1): ((0, 1, 0), (0, 0, 1), (-1, 0, 0)),    # U, F, L
    (-1, 1, -1): ((0, 1, 0), (-1, 0, 0), (0, 0, -1)),  # U, L, B
    (1, 1, -1): ((0, 1, 0), (0, 0, -1), (1, 0, 0)),    # U, B, R
    (1, -1, 1): ((0, -1, 0), (0, 0, 1), (1, 0, 0)),    # D, F, R
    (-1, -1, 1): ((0, -1, 0), (-1, 0, 0), (0, 0, 1)),  # D, L, F
    (-1, -1, -1): ((0, -1, 0), (0, 0, -1), (-1, 0, 0)),  # D, B, L
    (1, -1, -1): ((0, -1, 0), (1, 0, 0), (0, 0, -1)),  # D, R, B
}

# Fast piece-index lookup tables.
EDGE_INDEX: dict[frozenset, int] = {frozenset(e): i for i, e in enumerate(EDGES)}

#: Piece color triples in slot-frame cyclic order (U/D color first).
CORNER_INDEX: dict[tuple[str, str, str], int] = {
    ("U", "R", "F"): 0, ("U", "F", "L"): 1,
    ("U", "L", "B"): 2, ("U", "B", "R"): 3,
    ("D", "F", "R"): 4, ("D", "L", "F"): 5,
    ("D", "B", "L"): 6, ("D", "R", "B"): 7,
}


class InvalidCubeError(ValueError):
    """Raised when a cube state cannot exist on a legally scrambled cube."""


def _piece_colors(cubie) -> tuple[str, ...]:
    """The cubie's colors in its intrinsic sticker order (chirality!)."""
    return tuple(color for _, color in cubie.stickers)


def _edge_flip(cubie, slot) -> int:
    """1 if the edge piece is flipped relative to its current slot.

    Standard orientation convention: the piece's "key sticker" (its U/D
    color if it has one, otherwise its F/B color) must face the slot's own
    axis -- +-y for U/D-layer slots, +-z for E-slice slots.  With this
    convention U/D/R/L moves never change orientation values and each F/B
    quarter turn flips exactly its four ring edges (even parity invariant).
    """
    colors = set(color for _, color in cubie.stickers)
    if "U" in colors or "D" in colors:
        key = "U" if "U" in colors else "D"
    else:
        key = "F" if "F" in colors else "B"
    world = cubie.world_normal(next(n for n, c in cubie.stickers if c == key))
    slot_axis = 1 if slot[1] != 0 else 2  # y for U/D-layer, z for E-slice
    return 0 if world[slot_axis] != 0 else 1


def _permutation_parity(permutation: list[int]) -> int:
    """Parity (0 = even, 1 = odd) of a permutation written as target indices."""
    seen = [False] * len(permutation)
    parity = 0
    for start in range(len(permutation)):
        if seen[start]:
            continue
        cycle_len = 0
        j = start
        while not seen[j]:
            seen[j] = True
            j = permutation[j]
            cycle_len += 1
        parity ^= (cycle_len - 1) & 1
    return parity


def validate(state: CubeState) -> None:
    """Raise :class:`InvalidCubeError` if ``state`` is not a legal cube.

    Returns normally when the state is valid.
    """
    facelets = state.facelets()

    # 1. Color counts.
    counts: dict[str, int] = {}
    for row in facelets.values():
        for color in row:
            counts[color] = counts.get(color, 0) + 1
    if any(counts.get(f, 0) != 9 for f in ("U", "R", "F", "D", "L", "B")):
        raise InvalidCubeError(
            f"Each color must appear exactly 9 times, got {counts}"
        )

    # 2. Piece identity and 3./4. orientation & parity invariants.
    edge_perm = [-1] * 12
    corner_perm = [-1] * 8
    flip_sum = 0
    twist_sum = 0

    for i, slot in enumerate(EDGE_HOME):
        cubie = state.cubie_at(slot)
        colors = _piece_colors(cubie)
        idx = EDGE_INDEX.get(frozenset(colors))
        if idx is None:
            raise InvalidCubeError(
                f"Impossible edge color pair {sorted(colors)} at {slot}"
            )
        edge_perm[i] = idx
        flip_sum += _edge_flip(cubie, slot)

    for i, slot in enumerate(CORNER_HOME):
        cubie = state.cubie_at(slot)
        colors = [cubie.sticker_facing(d) for d in CORNER_SLOT_DIRS[slot]]
        if any(c is None for c in colors):
            raise InvalidCubeError(
                f"Corrupt corner at {slot}: stickers do not face outward"
            )
        try:
            i0 = colors.index("U") if "U" in colors else colors.index("D")
        except ValueError as exc:  # pragma: no cover - defensive
            raise InvalidCubeError(f"Corner at {slot} has no U/D sticker") from exc
        twist_sum += i0
        piece = (colors[i0], colors[(i0 + 1) % 3], colors[(i0 + 2) % 3])
        idx = CORNER_INDEX.get(piece)
        if idx is None:
            raise InvalidCubeError(
                f"Impossible corner color triple {piece} at {slot} "
                "(mirrored piece)"
            )
        corner_perm[i] = idx

    if -1 in edge_perm:
        raise InvalidCubeError("Edge pieces are not all distinct")
    if -1 in corner_perm:
        raise InvalidCubeError("Corner pieces are not all distinct")

    # 3. Orientation invariants.
    if flip_sum % 2 != 0:
        raise InvalidCubeError("Odd edge flip parity (impossible orientation)")
    if twist_sum % 3 != 0:
        raise InvalidCubeError("Corner twist sum not divisible by 3")

    # 4. Permutation parity must match between edges and corners.
    if _permutation_parity(edge_perm) != _permutation_parity(corner_perm):
        raise InvalidCubeError(
            "Edge and corner permutation parities differ (single swap)"
        )
