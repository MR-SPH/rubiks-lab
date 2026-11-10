"""Software 3D renderer for the Rubik's cube.

Renders the cube with a painter's-algorithm pipeline on top of QPainter:
numpy transforms the geometry, per-quad depth sorting resolves visibility,
and a small Lambert + Blinn specular model shades every quad.  A soft
contact shadow and a gradient backdrop are painted around the cube.

Why a software renderer instead of OpenGL: the scene is a small closed
set of polygons (~150 quads), so a vectorised numpy + QPainter pipeline
runs comfortably at 60 fps on ordinary hardware while being completely
free of GPU-driver quirks, works over remote desktops and in VMs, and
makes headless testing and screenshots trivial.

The renderer never mutates the logical cube state; it reads cubie
positions/orientations and at most one clean animation overlay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from core.cube import CubeState

#: Sticker palette (face letter -> RGB).
STICKER_COLORS: dict[str, tuple[int, int, int]] = {
    "U": (243, 246, 249),   # white
    "D": (255, 213, 3),     # yellow
    "F": (0, 156, 73),      # green
    "B": (0, 81, 186),      # blue
    "R": (186, 22, 55),     # red
    "L": (255, 96, 10),     # orange
}

#: Plastic body color.
BODY_COLOR = np.array([34.0, 38.0, 49.0])

#: Geometry constants (cube cell = 1.0).
BOX_HALF = 0.465          # cubie half size (leaves a visible gap)
STICKER_MARGIN = 0.105    # sticker inset from the cubie edge
STICKER_LIFT = 0.014      # sticker offset above the box face
CORNER_RADIUS = 0.085
ARC_SEGMENTS = 5          # per corner of the rounded sticker

#: Lighting (world space).
_LIGHT = np.array([0.40, 0.90, 0.52])
LIGHT_DIR = _LIGHT / np.linalg.norm(_LIGHT)
AMBIENT = 0.46
DIFFUSE = 0.58
SPECULAR = 0.30
SPEC_POWER = 22.0

#: Tangent frame per face direction (u, v) for building face geometry.
_FACE_FRAME: dict[tuple[int, int, int], tuple[np.ndarray, np.ndarray]] = {
    (0, 1, 0): (np.array([1.0, 0, 0]), np.array([0, 0, 1.0])),     # U
    (0, -1, 0): (np.array([1.0, 0, 0]), np.array([0, 0, -1.0])),   # D
    (0, 0, 1): (np.array([1.0, 0, 0]), np.array([0, 1.0, 0])),     # F
    (0, 0, -1): (np.array([-1.0, 0, 0]), np.array([0, 1.0, 0])),   # B
    (1, 0, 0): (np.array([0, 0, -1.0]), np.array([0, 1.0, 0])),    # R
    (-1, 0, 0): (np.array([0, 0, 1.0]), np.array([0, 1.0, 0])),    # L
}


def _rounded_sticker_polygon(half: float, radius: float) -> np.ndarray:
    """Rounded-square sticker outline in face-local 2D coordinates."""
    inner = half - radius
    pts = []
    # (cx, cy, arc start angle); each corner sweeps +90 degrees so the
    # outline runs top edge -> right edge -> bottom edge -> left edge.
    corners = [
        (inner, inner, 0.0),
        (-inner, inner, math.pi / 2),
        (-inner, -inner, math.pi),
        (inner, -inner, 1.5 * math.pi),
    ]
    for cx, cy, start in corners:
        for i in range(ARC_SEGMENTS + 1):
            a = start + (math.pi / 2) * i / ARC_SEGMENTS
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return np.array(pts)


#: Shared sticker outline (2D, local face plane).
_STICKER_2D = _rounded_sticker_polygon(
    BOX_HALF - STICKER_MARGIN, CORNER_RADIUS
)


@dataclass
class Quad:
    """One drawable polygon with shading and picking metadata."""

    points: np.ndarray            # (K, 3) world coordinates
    normal: np.ndarray            # world-space normal (shading)
    color: np.ndarray             # base RGB 0..255
    is_sticker: bool = False
    hovered: bool = False
    # Picking metadata (stickers only):
    cubie_home: tuple | None = None
    cubie_pos: tuple | None = None
    local_normal: tuple | None = None
    world_normal: np.ndarray | None = None
    world_center: np.ndarray | None = None


class CubeRenderer:
    """Builds the world-space quad list for the current frame."""

    def __init__(self) -> None:
        # Sticker local polygons per cubie home position:
        # home -> list of (points (K,3) local, normal tuple, color str)
        self._sticker_local: dict[tuple, list] = {}

    # -- geometry ------------------------------------------------------------------

    def build_local_geometry(self, state: CubeState) -> None:
        """Precompute sticker local polygons (once per session)."""
        self._sticker_local.clear()
        plane = BOX_HALF + STICKER_LIFT
        for home, cubie in state.cubies.items():
            entries = []
            for normal, color in cubie.stickers:
                u, v = _FACE_FRAME[normal]
                # _STICKER_2D coordinates are already in face units
                # (spanning +-(BOX_HALF - STICKER_MARGIN)).
                pts = np.array([
                    np.array(normal, dtype=float) * plane + u * pu + v * pv
                    for pu, pv in _STICKER_2D
                ])
                entries.append((pts, normal, color))
            self._sticker_local[home] = entries

    # -- frame building ----------------------------------------------------------------

    def build_scene(
        self,
        state: CubeState,
        anim_axis: int | None = None,
        anim_layer: int = 0,
        anim_angle: float = 0.0,
        hover: tuple | None = None,
    ) -> list[Quad]:
        """Build all quads for the current frame.

        ``hover`` is a ``(cubie_home, local_normal)`` pair identifying the
        sticker under the cursor (highlighted).
        """
        quads: list[Quad] = []
        half = BOX_HALF
        cos_a = math.cos(anim_angle)
        sin_a = math.sin(anim_angle)
        animate = anim_axis is not None and anim_angle != 0.0

        for pos, cubie in state.cubies.items():
            px, py, pz = pos
            overlay = animate and pos[anim_axis] == anim_layer

            def rot(pts: np.ndarray) -> np.ndarray:
                if overlay:
                    return _rotate_points(pts, anim_axis, cos_a, sin_a)
                return pts

            ori = np.array(cubie.ori, dtype=float)

            # Plastic body faces.  A cubie's exposed faces are the faces
            # where one of its stickers sits; their *world* directions are
            # the cubie orientation applied to the sticker local normals.
            # (Using local normals directly would misplace the plastic the
            # moment the cubie is rotated.)
            for normal, _scolor in cubie.stickers:
                wn = ori @ np.array(normal, dtype=float)
                u, v = _FACE_FRAME[tuple(int(round(c)) for c in wn)]
                nx, ny, nz = wn
                center = np.array([px + nx * half, py + ny * half, pz + nz * half])
                corners = np.array([
                    center + u * half + v * half,
                    center - u * half + v * half,
                    center - u * half - v * half,
                    center + u * half - v * half,
                ])
                quads.append(
                    Quad(
                        points=rot(corners),
                        normal=rot(wn[None, :])[0],
                        color=BODY_COLOR.copy(),
                    )
                )

            # Stickers: local polygon -> cubie orientation -> position.
            for local_pts, local_n, scolor in self._sticker_local[cubie.home]:
                pts = rot(local_pts @ ori.T + np.array([px, py, pz]))
                world_n = rot((ori @ np.array(local_n, dtype=float))[None, :])[0]
                is_hover = hover == (cubie.home, local_n)
                quads.append(
                    Quad(
                        points=pts,
                        normal=world_n,
                        color=np.array(STICKER_COLORS[scolor], dtype=float),
                        is_sticker=True,
                        hovered=is_hover,
                        cubie_home=cubie.home,
                        cubie_pos=pos,
                        local_normal=local_n,
                        world_normal=world_n,
                        world_center=pts.mean(axis=0),
                    )
                )
        return quads


def shade_color(base: np.ndarray, normal: np.ndarray, view_dir: np.ndarray,
                hovered: bool) -> tuple[int, int, int]:
    """Lambert + Blinn specular shading for one quad."""
    diffuse = max(0.0, float(np.dot(normal, LIGHT_DIR)))
    half_vec = LIGHT_DIR + view_dir
    norm = np.linalg.norm(half_vec)
    spec = 0.0
    if norm > 1e-9 and diffuse > 0.0:
        spec = SPECULAR * pow(max(0.0, float(np.dot(normal, half_vec / norm))),
                              SPEC_POWER)
    level = AMBIENT + DIFFUSE * diffuse + spec
    rgb = np.clip(base * level, 0, 255)
    if hovered:
        rgb = np.clip(rgb * 1.22 + 12, 0, 255)
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _rotate_points(pts: np.ndarray, axis: int, cos_a: float, sin_a: float) -> np.ndarray:
    """Rotate (N,3) points about the given world axis through the origin."""
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    if axis == 0:      # x
        return np.stack([x, y * cos_a - z * sin_a, y * sin_a + z * cos_a], axis=1)
    if axis == 1:      # y
        return np.stack([x * cos_a + z * sin_a, y, -x * sin_a + z * cos_a], axis=1)
    return np.stack([x * cos_a - y * sin_a, x * sin_a + y * cos_a, z], axis=1)  # z
