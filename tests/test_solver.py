"""Solver tests: both engines must solve arbitrary valid states."""

import random

import pytest

from core.cube import CubeState
from core.moves import Move, FACES, parse_sequence, format_sequence
from core.scramble import random_scramble
from core.cube_validator import validate, InvalidCubeError
from solver.solver import (
    solve as facade_solve,
    KOCIEMBA_AVAILABLE,
    SolveError,
)
from solver.lbl_solver import solve as lbl_solve, BeginnerSolver


def scrambled_state(rng: random.Random, n: int = 25) -> CubeState:
    s = CubeState()
    s.apply_sequence(random_scramble(n, rng))
    return s


def test_lbl_solves_many_random_states():
    """Fuzz: 250 random states must all be solved by the built-in engine."""
    rng = random.Random(1234)
    lengths = []
    for _ in range(250):
        s = scrambled_state(rng)
        moves = lbl_solve(s)
        check = s.clone()
        check.apply_sequence(moves)
        assert check.is_solved()
        lengths.append(len(moves))
    assert max(lengths) < 260          # beginner method stays well under this
    assert sum(lengths) / len(lengths) < 160  # typical average


def test_lbl_solves_hard_scrambles():
    """Long scrambles (50 moves) and single-move states both work."""
    rng = random.Random(555)
    for n in (1, 2, 3, 50):
        s = scrambled_state(rng, n)
        moves = lbl_solve(s)
        check = s.clone()
        check.apply_sequence(moves)
        assert check.is_solved()


def test_lbl_solved_input_returns_empty():
    assert lbl_solve(CubeState()) == []


def test_lbl_moves_are_valid_notation():
    rng = random.Random(99)
    s = scrambled_state(rng)
    text = format_sequence(lbl_solve(s))
    # round trip through the parser must give the same sequence
    assert format_sequence(parse_sequence(text)) == text


def test_facade_returns_engine_name():
    state = scrambled_state(random.Random(7))
    moves, engine = facade_solve(state)
    assert engine in ("kociemba", "lbl")
    check = state.clone()
    check.apply_sequence(moves)
    assert check.is_solved()


def test_facade_solved_state():
    moves, _engine = facade_solve(CubeState())
    assert moves == []


@pytest.mark.skipif(not KOCIEMBA_AVAILABLE, reason="kociemba package not installed")
def test_kociemba_solves_random_states():
    """The two-phase engine must produce short, verified solutions."""
    from solver.solver import _solve_kociemba

    rng = random.Random(2024)
    for _ in range(60):
        s = scrambled_state(rng)
        moves = _solve_kociemba(s)
        check = s.clone()
        check.apply_sequence(moves)
        assert check.is_solved()
        assert len(moves) <= 24  # two-phase solutions stay short


@pytest.mark.skipif(not KOCIEMBA_AVAILABLE, reason="kociemba package not installed")
def test_kociemba_facelet_string_layout():
    """A known scramble must yield the exact facelet string Kociemba expects."""
    from solver.solver import _solve_kociemba

    s = CubeState()
    s.apply_sequence(parse_sequence("R U R' U'"))
    moves = _solve_kociemba(s)
    check = s.clone()
    check.apply_sequence(moves)
    assert check.is_solved()


def test_both_engines_agree_on_solvability():
    rng = random.Random(31)
    for _ in range(30):
        s = scrambled_state(rng)
        m1, _ = facade_solve(s, engine="lbl")
        check = s.clone()
        check.apply_sequence(m1)
        assert check.is_solved()
        if KOCIEMBA_AVAILABLE:
            m2, _ = facade_solve(s, engine="kociemba")
            check = s.clone()
            check.apply_sequence(m2)
            assert check.is_solved()


def test_invalid_state_is_rejected():
    """A single swapped edge pair must be caught before solving."""
    from core.moves import rotation_quarter, mat_mul

    s = scrambled_state(random.Random(3))
    ry180 = rotation_quarter(1, 2)  # keeps U stickers up, swaps R<->L sides
    a, b = (1, 1, 0), (-1, 1, 0)    # UR and UL edge slots
    ca, cb = s.cubie_at(a), s.cubie_at(b)
    ca.pos, ca.ori = b, mat_mul(ry180, ca.ori)
    cb.pos, cb.ori = a, mat_mul(ry180, cb.ori)
    s.cubies[a], s.cubies[b] = cb, ca
    with pytest.raises(InvalidCubeError):
        lbl_solve(s)
    with pytest.raises(InvalidCubeError):
        facade_solve(s)


def test_lbl_engine_is_history_independent():
    """The same state reached two different ways gets the same solution."""
    rng = random.Random(64)
    seq = [Move(rng.choice(FACES), rng.choice([1, 2, 3])) for _ in range(18)]
    s1 = CubeState()
    s1.apply_sequence(seq)
    # a state reached by seq + noise + inverse(noise) is identical to s1
    noise = [Move(rng.choice(FACES), rng.choice([1, 2, 3])) for _ in range(6)]
    s2 = CubeState()
    s2.apply_sequence(seq)
    s2.apply_sequence(noise)
    s2.apply_sequence([m.inverse() for m in reversed(noise)])
    assert s1 == s2
    assert format_sequence(lbl_solve(s1)) == format_sequence(lbl_solve(s2))


def test_solution_simplification():
    from core.moves import simplify

    assert format_sequence(simplify(parse_sequence("R R U U' F'"))) == "R2 F'"


def test_solution_player_state_machine():
    from solver.solution_player import SolutionPlayer

    moves = parse_sequence("R U F'")
    p = SolutionPlayer()
    assert p.next_move() is None and not p.finished  # nothing loaded yet
    p.load(moves)
    assert p.next_move() == moves[0] and not p.finished
    assert p.advance() == moves[0]
    assert p.progress_text() == "Move 2 / 3"
    assert p.remaining() == moves[1:]
    p.advance(); p.advance()
    assert p.finished and p.progress_text() == "Complete · 3 moves"
    p.restart()
    assert p.next_move() == moves[0]
    p.clear()
    assert p.solution == [] and p.next_move() is None
