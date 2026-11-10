"""Cube state invariants: validity, facelets, solved detection, corruption."""

import random

import pytest

from core.cube import CubeState, FACELET_POSITIONS
from core.moves import Move, FACES, parse_sequence
from core.cube_validator import validate, InvalidCubeError, EDGES


def random_state(rng: random.Random, n: int = 25) -> CubeState:
    s = CubeState()
    for _ in range(n):
        s.apply(Move(rng.choice(FACES), rng.choice([1, 2, 3])))
    return s


def test_solved_cube_is_valid_and_detected():
    s = CubeState()
    validate(s)
    assert s.is_solved()


def test_26_cubies_present():
    s = CubeState()
    assert len(s.cubies) == 26
    centers = sum(1 for c in s.cubies.values() if len(c.stickers) == 1)
    edges = sum(1 for c in s.cubies.values() if len(c.stickers) == 2)
    corners = sum(1 for c in s.cubies.values() if len(c.stickers) == 3)
    assert (centers, edges, corners) == (6, 12, 8)


def test_facelet_string_layout():
    s = CubeState()
    assert s.facelet_string() == "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"


def test_facelets_centers_fixed():
    rng = random.Random(3)
    for _ in range(20):
        s = random_state(rng)
        f = s.facelets()
        for face in ("U", "R", "F", "D", "L", "B"):
            assert f[face][4] == face


def test_facelets_consistent_two_derivations():
    """Position-table lookup and brute-force sticker scan must agree."""
    rng = random.Random(11)
    for _ in range(25):
        s = random_state(rng)
        f = s.facelets()
        for face, positions in FACELET_POSITIONS.items():
            normal = {
                "U": (0, 1, 0), "D": (0, -1, 0),
                "F": (0, 0, 1), "B": (0, 0, -1),
                "R": (1, 0, 0), "L": (-1, 0, 0),
            }[face]
            for i, pos in enumerate(positions):
                cubie = s.cubie_at(pos)
                assert cubie.sticker_facing(normal) == f[face][i]


def test_validity_preserved_under_random_walks():
    rng = random.Random(4242)
    for _ in range(120):
        s = random_state(rng, n=40)
        validate(s)  # must not raise


def test_validator_rejects_swapped_edge_pair():
    """Swapping the UR and UL edge pieces breaks permutation parity."""
    from core.moves import rotation_quarter, mat_mul
    s = CubeState()
    s.apply_sequence(parse_sequence("R U F D L B"))
    ry180 = rotation_quarter(1, 2)  # 180 deg about y keeps U stickers up
    ur, ul = s.cubie_at((1, 1, 0)), s.cubie_at((-1, 1, 0))
    ur.pos, ur.ori = (-1, 1, 0), mat_mul(ry180, ur.ori)
    ul.pos, ul.ori = (1, 1, 0), mat_mul(ry180, ul.ori)
    s.cubies[(1, 1, 0)], s.cubies[(-1, 1, 0)] = ul, ur
    with pytest.raises(InvalidCubeError):
        validate(s)


def test_validator_rejects_twisted_corner():
    """Rotating one corner 120 deg about its body diagonal breaks twists."""
    from core.moves import mat_mul
    s = random_state(random.Random(5))
    cubie = s.cubie_at((1, 1, 1))
    # Pure 120-degree rotation about the (1,1,1) body diagonal: x->y->z->x.
    twist = ((0, 0, 1), (1, 0, 0), (0, 1, 0))
    cubie.ori = mat_mul(twist, cubie.ori)
    with pytest.raises(InvalidCubeError):
        validate(s)


def test_validator_rejects_flipped_edge():
    s = random_state(random.Random(6))
    cubie = s.cubie_at((0, 1, 1))
    # Mirror the edge's orientation by swapping two of its sticker normals.
    (n1, c1), (n2, c2) = cubie.stickers
    cubie.stickers = ((n1, c2), (n2, c1))
    with pytest.raises(InvalidCubeError):
        validate(s)


def test_validator_rejects_bad_color_counts():
    s = CubeState()
    cubie = s.cubie_at((1, 1, 1))
    cubie.stickers = ((cubie.stickers[0][0], "R"),) + cubie.stickers[1:]
    with pytest.raises(InvalidCubeError):
        validate(s)


def test_state_equality_and_clone():
    rng = random.Random(8)
    s = random_state(rng)
    t = s.clone()
    assert s == t
    t.apply(Move("R", 1))
    assert s != t
    t2 = s.clone()
    t2.apply(Move("R", 1))
    assert t == t2


def test_reset_returns_to_solved():
    rng = random.Random(9)
    s = random_state(rng)
    s.reset()
    assert s.is_solved()


def test_dict_positions_consistent_with_cubies():
    """The position->cubie map must always agree with each cubie's .pos."""
    rng = random.Random(77)
    s = random_state(rng, n=50)
    for pos, cubie in s.cubies.items():
        assert cubie.pos == pos
    s.reset()
    for pos, cubie in s.cubies.items():
        assert cubie.pos == pos
    assert s.is_solved()


def test_move_matrix_is_exact_rotation():
    from core.moves import move_matrix, Move
    m = move_matrix(Move("U", 1))
    det = (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
    assert det == 1  # proper rotation
    assert all(v in (-1, 0, 1) for row in m for v in row)  # exact integers
