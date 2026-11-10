"""Cubie data model.

The :class:`Cubie` class lives in :mod:`core.cube` because it is an
implementation detail of :class:`core.cube.CubeState` (its position
bookkeeping is tightly coupled to the state's position map).  This module
re-exports it so the documented package layout holds and so tests/tools
can import it from the natural place.
"""

from .cube import Cubie, CUBIE_POSITIONS

__all__ = ["Cubie", "CUBIE_POSITIONS"]
