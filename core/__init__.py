"""RUBIK'S LAB core cube engine.

Pure-Python, exact (integer) logical representation of a 3x3x3 cube.
No Qt and no floating point here: this is the single source of truth
that the renderer, solver and UI all agree on.
"""

from .cube import CubeState, Cubie, FACELET_POSITIONS
from .moves import (
    FACES,
    Move,
    format_sequence,
    invert_sequence,
    move_matrix,
    parse_sequence,
    shift_face,
    simplify,
)
from .cube_validator import InvalidCubeError, validate
from .scramble import random_scramble

__all__ = [
    "CubeState",
    "Cubie",
    "FACELET_POSITIONS",
    "FACES",
    "Move",
    "InvalidCubeError",
    "format_sequence",
    "invert_sequence",
    "move_matrix",
    "parse_sequence",
    "random_scramble",
    "shift_face",
    "simplify",
    "validate",
]
