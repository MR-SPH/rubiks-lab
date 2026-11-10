"""Unit tests for face turns: exact effects of every one of the 18 moves."""

import pytest

from core.cube import CubeState
from core.moves import Move, FACES, parse_sequence, format_sequence, shift_face, simplify


def state_after(*moves) -> CubeState:
    s = CubeState()
    s.apply_sequence(moves)
    return s


@pytest.mark.parametrize("face", FACES)
@pytest.mark.parametrize("turns", [1, 2, 3])
def test_every_move_then_inverse_restores_solved(face, turns):
    s = CubeState()
    s.apply(Move(face, turns))
    assert not s.is_solved() or turns == 0
    s.apply(Move(face, turns).inverse())
    assert s.is_solved()


@pytest.mark.parametrize("face", FACES)
@pytest.mark.parametrize("turns", [1, 2, 3])
def test_four_quarter_turns_restore(face, turns):
    """X applied four times (and X2 twice) must return to solved."""
    s = CubeState()
    for _ in range(4):
        s.apply(Move(face, 1))
    assert s.is_solved()


@pytest.mark.parametrize("face", FACES)
def test_two_half_turns_restore(face):
    s = CubeState()
    s.apply(Move(face, 2))
    s.apply(Move(face, 2))
    assert s.is_solved()


@pytest.mark.parametrize("face", FACES)
def test_half_turn_equals_two_quarter_turns(face):
    s1 = state_after(Move(face, 1), Move(face, 1))
    s2 = state_after(Move(face, 2))
    assert s1 == s2


def test_piece_cycles_u():
    """U (clockwise from above) cycles UF -> UL -> UB -> UR and URF -> UFL."""
    s = state_after(Move("U", 1))
    assert s.cubie_at((-1, 1, 1)).home == (1, 1, 1)      # URF -> UFL
    assert s.cubie_at((-1, 1, 0)).home == (0, 1, 1)      # UF -> UL
    assert s.cubie_at((0, 1, -1)).home == (-1, 1, 0)     # UL -> UB
    assert s.cubie_at((1, 1, 0)).home == (0, 1, -1)      # UB -> UR


def test_piece_cycles_r():
    """R cycles URF -> URB -> DRB -> DRF and FR -> UR -> BR -> DR."""
    s = state_after(Move("R", 1))
    assert s.cubie_at((1, 1, -1)).home == (1, 1, 1)      # URF -> URB
    assert s.cubie_at((1, -1, -1)).home == (1, 1, -1)    # URB -> DRB
    assert s.cubie_at((1, -1, 1)).home == (1, -1, -1)    # DRB -> DRF
    assert s.cubie_at((1, 1, 0)).home == (1, 0, 1)       # FR -> UR
    assert s.cubie_at((1, 0, -1)).home == (1, 1, 0)      # UR -> BR


def test_piece_cycles_f():
    """F cycles UF -> FR -> DF -> FL and ULF -> URF -> DRF -> DLF."""
    s = state_after(Move("F", 1))
    assert s.cubie_at((1, 0, 1)).home == (0, 1, 1)       # UF -> FR
    assert s.cubie_at((0, -1, 1)).home == (1, 0, 1)      # FR -> DF
    assert s.cubie_at((1, 1, 1)).home == (-1, 1, 1)      # ULF -> URF


def test_facelet_effect_u():
    """After U, the F top row shows the old R top row (classic check)."""
    s = state_after(Move("U", 1))
    f = s.facelets()
    assert f["F"][:3] == ["R", "R", "R"]
    assert f["L"][:3] == ["F", "F", "F"]
    assert f["B"][:3] == ["L", "L", "L"]
    assert f["R"][:3] == ["B", "B", "B"]
    assert f["U"] == ["U"] * 9


def test_facelet_effect_r():
    """After R, the U right column shows the old F right column."""
    s = state_after(Move("R", 1))
    f = s.facelets()
    assert [f["U"][2], f["U"][5], f["U"][8]] == ["F", "F", "F"]
    assert [f["B"][0], f["B"][3], f["B"][6]] == ["U", "U", "U"]
    assert [f["D"][2], f["D"][5], f["D"][8]] == ["B", "B", "B"]
    assert [f["F"][2], f["F"][5], f["F"][8]] == ["D", "D", "D"]
    assert f["R"] == ["R"] * 9


def test_facelet_effect_f():
    """After F, the U bottom row shows the old L right column (L colors)."""
    s = state_after(Move("F", 1))
    f = s.facelets()
    assert f["U"][6:9] == ["L", "L", "L"]
    assert f["D"][0:3] == ["R", "R", "R"]
    assert f["F"] == ["F"] * 9


def test_centers_never_move():
    s = state_after(*parse_sequence("R U R' U' F2 D B' L"))
    for face_pos in [(0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0)]:
        cubie = s.cubie_at(face_pos)
        assert cubie.home == face_pos
        # Center sticker still faces outward.
        assert cubie.world_normal(cubie.stickers[0][0]) == face_pos


def test_notation_round_trip():
    text = "R U' F2 D L' B2 R2 U2 D' F'"
    moves = parse_sequence(text)
    assert format_sequence(moves) == text


def test_notation_primes_and_halves():
    moves = parse_sequence("R' R2 R2' R")
    assert [m.turns for m in moves] == [3, 2, 2, 1]


def test_notation_unicode_primes_and_quotes():
    moves = parse_sequence("R’ U′ F‘ L‵ B`")
    assert [m.turns for m in moves] == [3, 3, 3, 3, 3]
    assert [m.face for m in moves] == ["R", "U", "F", "L", "B"]


def test_notation_rejects_garbage():
    with pytest.raises(ValueError):
        parse_sequence("X2")
    with pytest.raises(ValueError):
        parse_sequence("R9")
    with pytest.raises(ValueError):
        parse_sequence("RU'")  # no space -> invalid token 'RU\''


def test_simplify_merges_and_cancels():
    moves = parse_sequence("R R U U' F F F")
    assert format_sequence(simplify(moves)) == "R2 F'"
    assert simplify(parse_sequence("R R R R")) == []
    assert format_sequence(simplify(parse_sequence("R U R R'"))) == "R U"


def test_shift_face_ring():
    assert shift_face("F", 1) == "R"
    assert shift_face("R", 1) == "B"
    assert shift_face("B", 1) == "L"
    assert shift_face("L", 1) == "F"
    assert shift_face("B", 2) == "F"
    assert shift_face("U", 3) == "U"
    assert shift_face("D", 1) == "D"
