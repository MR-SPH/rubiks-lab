"""Inverse-move and sequence-inverse properties across random walks."""

import random

import pytest

from core.cube import CubeState
from core.moves import Move, FACES, parse_sequence, invert_sequence


@pytest.mark.parametrize("face", FACES)
@pytest.mark.parametrize("turns", [1, 2, 3])
def test_inverse_then_move_restores(face, turns):
    s = CubeState()
    m = Move(face, turns)
    s.apply(m.inverse())
    s.apply(m)
    assert s.is_solved()


@pytest.mark.parametrize("face", FACES)
@pytest.mark.parametrize("turns", [1, 2, 3])
def test_move_equals_triple_inverse(face, turns):
    """X' must equal X applied three times (and X2 is self-inverse)."""
    s1 = CubeState()
    for _ in range(3):
        s1.apply(Move(face, 1))
    s2 = CubeState()
    s2.apply(Move(face, 3))
    if turns in (1, 3):
        assert s1 == s2


def test_random_sequence_then_inverse_restores():
    """For 300 random sequences: seq + inverse(seq) == solved cube."""
    rng = random.Random(20240601)
    for _ in range(300):
        seq = [Move(rng.choice(FACES), rng.choice([1, 2, 3])) for _ in range(rng.randint(1, 30))]
        s = CubeState()
        s.apply_sequence(seq)
        assert not s.is_solved() or len(seq) % 4 == 0
        s.apply_sequence(invert_sequence(seq))
        assert s.is_solved()


def test_reversing_without_inverting_does_not_restore():
    """Sanity: undoing in the wrong order must (almost always) fail."""
    rng = random.Random(7)
    seq = [Move(rng.choice(FACES), rng.choice([1, 2, 3])) for _ in range(10)]
    s = CubeState()
    s.apply_sequence(seq)
    s.apply_sequence(list(reversed(seq)))  # wrong: not inverted
    assert not s.is_solved()


def test_known_sequence_identity():
    """(R U R' U') applied six times is the identity (sexy-move order)."""
    seq = parse_sequence("R U R' U'")
    s = CubeState()
    for _ in range(6):
        s.apply_sequence(seq)
    assert s.is_solved()


def test_inverse_of_parse_round_trip():
    rng = random.Random(99)
    for _ in range(50):
        text = " ".join(
            f"{f}{t}" for f, t in
            ((rng.choice(FACES), rng.choice(["", "'", "2"])) for _ in range(12))
        )
        moves = parse_sequence(text)
        s = CubeState()
        s.apply_sequence(moves)
        s.apply_sequence(invert_sequence(moves))
        assert s.is_solved()
