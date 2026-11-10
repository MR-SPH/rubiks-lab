"""Solver package: real solving engines for any valid cube state."""

from .solver import (
    KOCIEMBA_AVAILABLE,
    ENGINE_LABELS,
    SolveError,
    engine_label,
    solve,
    solution_text,
)
