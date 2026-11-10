"""Scramble generator constraints and safety."""

import random

import pytest

from core.cube import CubeState
from core.moves import FACE_AXIS, format_sequence, invert_sequence
from core.scramble import random_scramble
from core.cube_validator import validate


def test_scramble_length_and_format():
    rng = random.Random(1)
    for n in (1, 5, 25, 40):
        moves = random_scramble(n, rng)
        assert len(moves) == n
        assert len(format_sequence(moves).split()) == n


def test_no_consecutive_same_face():
    rng = random.Random(2)
    for _ in range(200):
        moves = random_scramble(25, rng)
        for a, b in zip(moves, moves[1:]):
            assert a.face != b.face


def test_no_same_axis_aba_pattern():
    rng = random.Random(3)
    for _ in range(200):
        moves = random_scramble(25, rng)
        for a, b, c in zip(moves, moves[1:], moves[2:]):
            if FACE_AXIS[c.face] == FACE_AXIS[a.face] == FACE_AXIS[b.face]:
                pytest.fail(f"wasted move pattern {a} {b} {c}")


def test_scramble_is_deterministic_with_seed():
    m1 = random_scramble(25, random.Random(123))
    m2 = random_scramble(25, random.Random(123))
    assert format_sequence(m1) == format_sequence(m2)


def test_scramble_does_not_corrupt_cube():
    rng = random.Random(4)
    for _ in range(50):
        s = CubeState()
        s.apply_sequence(random_scramble(25, rng))
        validate(s)


def test_scramble_leaves_cube_unsolved():
    rng = random.Random(5)
    for _ in range(50):
        s = CubeState()
        s.apply_sequence(random_scramble(20, rng))
        assert not s.is_solved()


def test_inverse_scramble_restores_solved():
    rng = random.Random(6)
    for _ in range(30):
        moves = random_scramble(25, rng)
        s = CubeState()
        s.apply_sequence(moves)
        s.apply_sequence(invert_sequence(moves))
        assert s.is_solved()


def test_invalid_length_rejected():
    with pytest.raises(ValueError):
        random_scramble(0)
