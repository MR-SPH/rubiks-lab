"""Orbit camera with smooth inertial motion and perspective projection.

The camera orbits the cube origin.  Angles and distance are stored both as
*current* values (what is rendered) and *target* values (where the user
wants them); every frame the current values ease towards the targets,
which gives buttery orbiting and zooming without extra code at call sites.
"""

from __future__ import annotations

import math

import numpy as np

#: Camera limits and defaults.
MIN_PITCH = 0.12          # radians above the horizon plane
MAX_PITCH = 1.45
MIN_DISTANCE = 4.2
MAX_DISTANCE = 11.0
DEFAULT_YAW = math.radians(33)
DEFAULT_PITCH = math.radians(24)
DEFAULT_DISTANCE = 8.8
FOV_DEGREES = 33.0

#: Slight downward look-at target keeps the cube optically centred
#: (the soft shadow below it needs room too).
LOOK_TARGET = np.array([0.0, -0.10, 0.0])

_LERP = 0.18              # easing factor per 16 ms frame


class OrbitCamera:
    """Smooth orbiting perspective camera."""

    def __init__(self) -> None:
        self.yaw = DEFAULT_YAW
        self.pitch = DEFAULT_PITCH
        self.distance = DEFAULT_DISTANCE
        self.target_yaw = DEFAULT_YAW
        self.target_pitch = DEFAULT_PITCH
        self.target_distance = DEFAULT_DISTANCE
        self._aspect = 1.0

    # -- input ----------------------------------------------------------------

    def orbit(self, dx: float, dy: float) -> None:
        """Rotate by mouse deltas (pixels)."""
        self.target_yaw += dx * 0.0088
        self.target_pitch += dy * 0.0088
        self.target_pitch = max(MIN_PITCH, min(MAX_PITCH, self.target_pitch))

    def zoom(self, steps: float) -> None:
        """Zoom by wheel steps (positive = closer)."""
        factor = math.pow(0.88, steps)
        self.target_distance = max(
            MIN_DISTANCE, min(MAX_DISTANCE, self.target_distance * factor)
        )

    def reset(self) -> None:
        self.target_yaw = DEFAULT_YAW
        self.target_pitch = DEFAULT_PITCH
        self.target_distance = DEFAULT_DISTANCE

    # -- per-frame update -------------------------------------------------------

    def update(self) -> None:
        """Ease current values towards their targets (call once per frame)."""
        k = _LERP
        self.yaw += (self.target_yaw - self.yaw) * k
        self.pitch += (self.target_pitch - self.pitch) * k
        self.distance += (self.target_distance - self.distance) * k

    # -- matrices ----------------------------------------------------------------

    def set_viewport(self, width: int, height: int) -> None:
        self._aspect = width / max(1, height)

    def eye(self) -> np.ndarray:
        cp = math.cos(self.pitch)
        return np.array(
            [
                self.distance * cp * math.sin(self.yaw),
                self.distance * math.sin(self.pitch),
                self.distance * cp * math.cos(self.yaw),
            ]
        )

    def view_matrix(self) -> np.ndarray:
        """4x4 world-to-camera matrix (looks at LOOK_TARGET)."""
        eye = self.eye()
        forward = LOOK_TARGET - eye
        forward = forward / np.linalg.norm(forward)
        up_hint = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, up_hint)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        m = np.eye(4)
        m[0, :3], m[1, :3], m[2, :3] = right, up, -forward
        m[0, 3] = -np.dot(right, eye)
        m[1, 3] = -np.dot(up, eye)
        m[2, 3] = np.dot(forward, eye)
        return m

    def projection_matrix(self) -> np.ndarray:
        """4x4 perspective projection matrix."""
        f = 1.0 / math.tan(math.radians(FOV_DEGREES) / 2)
        near, far = 0.1, 100.0
        m = np.zeros((4, 4))
        m[0, 0] = f / self._aspect
        m[1, 1] = f
        m[2, 2] = (far + near) / (near - far)
        m[2, 3] = 2 * far * near / (near - far)
        m[3, 2] = -1.0
        return m

    def matrix(self) -> np.ndarray:
        """Combined view-projection matrix."""
        return self.projection_matrix() @ self.view_matrix()

    def project(self, points: np.ndarray, width: int, height: int):
        """Project an (N,3) array of world points to (N,2) pixel coordinates.

        Returns ``(screen_points, view_z)``; view_z is negative in front of
        the camera and smaller (more negative) means farther away.
        """
        pts = np.asarray(points, dtype=float)
        homog = np.hstack([pts, np.ones((len(pts), 1))])
        clip = homog @ self.matrix().T
        with np.errstate(divide="ignore", invalid="ignore"):
            ndc = clip[:, :3] / clip[:, 3:4]
        screen = np.empty((len(pts), 2))
        screen[:, 0] = (ndc[:, 0] * 0.5 + 0.5) * width
        screen[:, 1] = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * height
        return screen, clip[:, 3]  # clip w = view-space depth scale
