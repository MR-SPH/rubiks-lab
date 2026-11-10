"""Solver facade: real solving engines for any valid cube state.

Primary engine: Herbert Kociemba's two-phase algorithm (via the optional
``kociemba`` package, which ships a compiled C implementation).  Fallback
engine: the pure-Python layer-by-layer solver in ``lbl_solver`` (always
available, no dependencies).

Both engines solve the cube from its *current state* -- neither has any
knowledge of how the state was reached, and neither reverses history.
"""

from __future__ import annotations

from core.cube import CubeState
from core.moves import Move, format_sequence, parse_sequence, simplify
from core.cube_validator import validate, InvalidCubeError
from .lbl_solver import BeginnerSolver, SolverError

try:  # optional dependency: pure fallback exists when missing
    import kociemba as _kociemba

    KOCIEMBA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    _kociemba = None
    KOCIEMBA_AVAILABLE = False


class SolveError(RuntimeError):
    """Raised when no engine could produce a valid solution."""


_ENGINES = ("auto", "kociemba", "lbl")

#: Human-readable name of each engine (for UI display).
ENGINE_LABELS = {
    "kociemba": "Kociemba two-phase",
    "lbl": "Layer-by-layer (built-in)",
}

#: Maximum accepted solution length for the two-phase engine.
_KOCIEMBA_MAX_DEPTH = 24


def engine_label(engine: str) -> str:
    """Display name of the engine that produced a solution."""
    if engine == "auto":
        engine = "kociemba" if KOCIEMBA_AVAILABLE else "lbl"
    return ENGINE_LABELS.get(engine, engine)


def solve(state: CubeState, engine: str = "auto") -> tuple[list[Move], str]:
    """Solve ``state`` with the requested engine.

    Returns ``(moves, engine_used)``.  ``engine`` may be ``"auto"``
    (prefer Kociemba, fall back to the built-in solver), ``"kociemba"``
    or ``"lbl"``.  Raises :class:`InvalidCubeError` for impossible states
    and :class:`SolveError` if no engine succeeds.
    """
    if engine not in _ENGINES:
        raise ValueError(f"Unknown engine {engine!r}")
    validate(state)
    if state.is_solved():
        return [], ("kociemba" if KOCIEMBA_AVAILABLE else "lbl")

    errors: list[str] = []
    order = []
    if engine == "auto":
        order = ["kociemba", "lbl"] if KOCIEMBA_AVAILABLE else ["lbl"]
    else:
        order = [engine]

    for name in order:
        try:
            if name == "kociemba":
                moves = _solve_kociemba(state)
            else:
                moves = _lbl_engine().solve(state)
            return moves, name
        except (SolveError, SolverError, ValueError) as exc:
            errors.append(f"{name}: {exc}")

    raise SolveError("No solver engine succeeded: " + "; ".join(errors))


def _solve_kociemba(state: CubeState) -> list[Move]:
    """Two-phase solver via the optional ``kociemba`` package."""
    if _kociemba is None:
        raise SolveError("kociemba package is not installed")
    facelets = state.facelet_string()
    try:
        raw = _kociemba.solve(facelets)
    except Exception as exc:  # the package raises ValueError for bad states
        raise SolveError(f"kociemba rejected the state: {exc}") from exc
    if not raw or raw.startswith("Error"):
        raise SolveError(f"kociemba failed: {raw!r}")
    moves = simplify(parse_sequence(raw))
    if len(moves) > _KOCIEMBA_MAX_DEPTH:
        raise SolveError(f"kociemba returned an implausible solution ({len(moves)})")
    # Final guarantee: the solution must actually solve the state.
    check = state.clone()
    check.apply_sequence(moves)
    if not check.is_solved():
        raise SolveError("kociemba solution failed verification")
    return moves


_LBL_ENGINE: BeginnerSolver | None = None


def _lbl_engine() -> BeginnerSolver:
    """Lazily-built shared layer-by-layer engine instance."""
    global _LBL_ENGINE
    if _LBL_ENGINE is None:
        _LBL_ENGINE = BeginnerSolver()
    return _LBL_ENGINE


def solution_text(moves: list[Move]) -> str:
    """Standard notation string for a solution."""
    return format_sequence(moves)


__all__ = [
    "SolveError",
    "SolverError",
    "KOCIEMBA_AVAILABLE",
    "ENGINE_LABELS",
    "solve",
    "engine_label",
    "solution_text",
    "InvalidCubeError",
]
