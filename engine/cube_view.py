"""Interactive 3D cube view widget.

Owns the camera, the animation queue and the renderer, and converts mouse
input into either camera orbiting or face-turn requests.  The widget is
strictly read-only towards the logical cube state:

* rendering reads the state every frame (the state is the truth);
* while a move animates, the renderer applies one clean rotation overlay;
* when an animation completes, ``moveCompleted`` fires and the window
  applies the move to the logical state and calls :meth:`resync` before
  the next queued animation starts -- so visuals can never drift from
  logic, even across hundreds of moves.
"""

from __future__ import annotations

import math
import time

import numpy as np

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from core.cube import CubeState
from core.moves import FACE_AXIS, FACE_NORMAL, FACE_SIGN, Move
from .animator import AnimationQueue
from .camera import OrbitCamera
from .renderer import CubeRenderer, Quad, shade_color, STICKER_COLORS

#: Tuning constants.
DRAG_THRESHOLD_PX = 9.0        # drag distance before a turn commits
DRAG_MATCH_COS = 0.72          # min alignment between drag and move tangent
DEFAULT_MOVE_MS = 230.0
SCRAMBLE_MOVE_MS = 85.0
HOVER_ACCENT = (38, 224, 224)


class CubeView(QWidget):
    """The central 3D workspace widget."""

    faceTurnRequested = Signal(object)          # Move (user dragged a sticker)
    moveCompleted = Signal(object, str)         # Move, source
    queueChanged = Signal(int)                  # pending count

    def __init__(self, state: CubeState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.setMinimumSize(320, 280)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.camera = OrbitCamera()
        self.animator = AnimationQueue()
        self.animator.on_complete = self._on_anim_complete
        self.animator.on_queue_changed = lambda: self.queueChanged.emit(
            self.animator.pending
        )
        self.renderer = CubeRenderer()
        self.renderer.build_local_geometry(state)

        self._speed_multiplier = 1.0
        self._show_labels = True
        self._hover: tuple | None = None
        self._pick_data: list[dict] = []
        self._drag: dict | None = None
        self._last_frame_time = time.perf_counter()

        self._timer = self._start_timer()

    # -- Qt setup ---------------------------------------------------------------

    def _start_timer(self):
        from PySide6.QtCore import QTimer

        timer = QTimer(self)
        timer.timeout.connect(self._on_frame)
        timer.start(16)
        return timer

    # -- public API -----------------------------------------------------------------

    def enqueue_move(self, move: Move, duration_ms: float | None = None,
                     source: str = "user") -> None:
        """Queue a move for animation (the logical state updates on finish)."""
        if duration_ms is None:
            duration_ms = DEFAULT_MOVE_MS / max(0.05, self._speed_multiplier)
        self.animator.enqueue(move, duration_ms, source)

    def enqueue_many(self, moves, duration_ms: float, source: str = "user") -> None:
        """Queue several moves at the same duration."""
        self.animator.enqueue_many(moves, duration_ms, source)

    def clear_queue(self) -> int:
        return self.animator.clear()

    def cancel_all(self) -> None:
        """Drop the queue and any in-flight animation (used by Reset)."""
        self.animator.cancel_all()
        self.update()

    def set_paused(self, paused: bool) -> None:
        self.animator.set_paused(paused)

    def resync(self) -> None:
        """Force a repaint from the (possibly changed) logical state."""
        self.update()

    def set_speed_multiplier(self, multiplier: float) -> None:
        self._speed_multiplier = max(0.05, float(multiplier))

    def set_show_labels(self, show: bool) -> None:
        self._show_labels = bool(show)
        self.update()

    @property
    def is_animating(self) -> bool:
        return self.animator.is_busy

    @property
    def pending_moves(self) -> int:
        return self.animator.pending

    @property
    def speed_multiplier(self) -> float:
        return self._speed_multiplier

    # -- animation completion ----------------------------------------------------------

    def _on_anim_complete(self, move: Move, source: str) -> None:
        # The window applies the logical move synchronously in this slot,
        # then calls resync(); afterwards the queue may start the next move.
        self.moveCompleted.emit(move, source)

    # -- painting --------------------------------------------------------------------------

    def _on_frame(self) -> None:
        now = time.perf_counter()
        dt_ms = (now - self._last_frame_time) * 1000.0
        self._last_frame_time = now
        busy = self.animator.is_busy or self.camera_needs_update()
        self.camera.update()
        self.animator.tick(min(dt_ms, 50.0))
        if busy or self.animator.is_busy or self._hover is not None:
            self.update()

    def camera_needs_update(self) -> bool:
        c = self.camera
        return (
            abs(c.yaw - c.target_yaw) > 1e-4
            or abs(c.pitch - c.target_pitch) > 1e-4
            or abs(c.distance - c.target_distance) > 1e-4
        )

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w, h = self.width(), self.height()
        self.camera.set_viewport(w, h)
        self._draw_background(painter, w, h)

        active = self.animator.active
        if active is not None:
            quads = self.renderer.build_scene(
                self._state,
                anim_axis=active.axis,
                anim_layer=active.move.layer,
                anim_angle=active.angle,
                hover=self._hover,
            )
        else:
            quads = self.renderer.build_scene(self._state, hover=self._hover)

        self._draw_shadow(painter, w, h)
        self._pick_data = self._draw_quads(painter, quads, w, h)
        if self._show_labels:
            self._draw_face_letters(painter, w, h)
        painter.end()

    def _draw_background(self, painter: QPainter, w: int, h: int) -> None:
        grad = QLinearGradient(0.0, 0.0, 0.0, float(h))
        grad.setColorAt(0.0, QColor("#101728"))
        grad.setColorAt(0.55, QColor("#0c1220"))
        grad.setColorAt(1.0, QColor("#080b13"))
        painter.fillRect(0, 0, w, h, QBrush(grad))

        # Soft teal glow behind the cube.
        cx, cy = w / 2, h * 0.44
        glow = QRadialGradient(cx, cy, min(w, h) * 0.42)
        glow.setColorAt(0.0, QColor(34, 211, 238, 26))
        glow.setColorAt(0.55, QColor(34, 211, 238, 8))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, w, h, QBrush(glow))

    def _draw_shadow(self, painter: QPainter, w: int, h: int) -> None:
        """Soft contact shadow under the cube."""
        center = np.array([[0.0, -2.12, 0.0]])
        ex = np.array([[2.05, -2.12, 0.0]])
        ez = np.array([[0.0, -2.12, 2.05]])
        c_scr, _ = self.camera.project(center, w, h)
        x_scr, _ = self.camera.project(ex, w, h)
        z_scr, _ = self.camera.project(ez, w, h)
        cx, cy = float(c_scr[0, 0]), float(c_scr[0, 1])
        rx = abs(float(x_scr[0, 0]) - cx)
        ry = abs(float(z_scr[0, 1]) - cy)
        if rx < 2 or ry < 2:
            return
        painter.save()
        painter.translate(cx, cy)
        painter.scale(rx, ry)
        grad = QRadialGradient(0.0, 0.0, 1.0)
        grad.setColorAt(0.0, QColor(0, 0, 0, 105))
        grad.setColorAt(0.55, QColor(0, 0, 0, 46))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), 1.0, 1.0)
        painter.restore()

    def _draw_quads(self, painter: QPainter, quads: list[Quad], w: int, h: int) -> list[dict]:
        eye = self.camera.eye()
        screen_data = []
        for quad in quads:
            centroid = quad.points.mean(axis=0)
            to_eye = eye - centroid
            # Back-face culling: skip polygons facing away from the camera.
            if float(np.dot(quad.normal, to_eye)) <= 1e-9:
                continue
            pts, clip_w = self.camera.project(quad.points, w, h)
            if np.any(clip_w <= 0.05):
                continue
            norm = np.linalg.norm(to_eye)
            view_dir = to_eye / norm if norm > 1e-9 else np.array([0.0, 0.0, 1.0])
            color = shade_color(quad.color, quad.normal, view_dir, quad.hovered)
            depth = float(np.mean(clip_w))
            screen_data.append((depth, quad, pts))

        # Painter's algorithm: farthest first (larger clip w = farther).
        screen_data.sort(key=lambda item: -item[0])

        pick: list[dict] = []
        for depth, quad, pts in screen_data:
            poly = QPolygonF([QPointF(float(x), float(y)) for x, y in pts])
            color = shade_color(
                quad.color,
                quad.normal,
                _view_dir(self.camera.eye(), quad.points),
                quad.hovered,
            )
            brush = QBrush(QColor(*color))
            if quad.hovered:
                painter.setPen(QPen(QColor(*HOVER_ACCENT, 230), 1.8))
            else:
                # Same-color hairline pen hides anti-aliasing seams.
                painter.setPen(QPen(QColor(*color), 0.9))
            painter.setBrush(brush)
            painter.drawPolygon(poly)

            if quad.is_sticker:
                pick.append(
                    {
                        "poly": poly,
                        "path": _path_from(poly),
                        "depth": depth,
                        "home": quad.cubie_home,
                        "cubie_pos": quad.cubie_pos,
                        "local_normal": quad.local_normal,
                        "world_normal": quad.world_normal,
                        "world_center": quad.world_center,
                        "color": quad.color,
                    }
                )
        return pick

    def _draw_face_letters(self, painter: QPainter, w: int, h: int) -> None:
        """Draw face letters on visible center stickers only."""
        painter.save()
        painter.setPen(QPen(QColor(10, 14, 22, 130)))
        eye = self.camera.eye()
        for pos, cubie in self._state.cubies.items():
            if len(cubie.stickers) != 1:
                continue
            normal, color = cubie.stickers[0]
            world_n = np.asarray(cubie.world_normal(normal), dtype=float)
            center = np.asarray(pos, dtype=float)
            # back-face culling: skip stickers facing away from the camera
            if np.dot(world_n, eye - center) <= 0:
                continue
            letter = color
            for entry in self._pick_data:
                if entry["home"] == cubie.home:
                    poly = entry["poly"]
                    rect = poly.boundingRect()
                    size = max(rect.width(), rect.height())
                    font = QFont()
                    font.setPixelSize(int(max(9, min(26, size * 0.44))))
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(rect, Qt.AlignCenter, letter)
                    break
        painter.restore()

    # -- picking ---------------------------------------------------------------------------

    def _pick_sticker(self, x: float, y: float) -> dict | None:
        best = None
        best_depth = None
        for entry in self._pick_data:
            if entry["path"].contains(QPointF(x, y)):
                if best_depth is None or entry["depth"] < best_depth:
                    best, best_depth = entry, entry["depth"]
        return best

    def _update_hover(self, x: float, y: float) -> None:
        entry = self._pick_sticker(x, y)
        new_hover = None
        if entry is not None and not self.animator.is_busy:
            new_hover = (entry["home"], entry["local_normal"])
        if new_hover != self._hover:
            self._hover = new_hover
            self.update()

    # -- mouse interaction ---------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        if event.button() == Qt.LeftButton:
            entry = (
                None
                if self.animator.is_busy
                else self._pick_sticker(pos.x(), pos.y())
            )
            if entry is not None:
                self._drag = {
                    "mode": "sticker",
                    "entry": entry,
                    "press": (pos.x(), pos.y()),
                    "committed": False,
                }
            else:
                self._drag = {"mode": "orbit", "last": (pos.x(), pos.y())}
        elif event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._drag = {"mode": "orbit", "last": (pos.x(), pos.y())}

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        if self._drag is None:
            self._update_hover(pos.x(), pos.y())
            return
        if self._drag["mode"] == "orbit":
            x0, y0 = self._drag["last"]
            self.camera.orbit(pos.x() - x0, pos.y() - y0)
            self._drag["last"] = (pos.x(), pos.y())
            self.update()
            return
        # sticker drag
        if self._drag["committed"]:
            return
        px, py = self._drag["press"]
        dx, dy = pos.x() - px, pos.y() - py
        dist = math.hypot(dx, dy)
        if dist < DRAG_THRESHOLD_PX:
            return
        move = self._drag_direction_move(dx, dy, self._drag["entry"])
        if move is not None:
            self._drag["committed"] = True
            self._hover = None
            self.faceTurnRequested.emit(move)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.camera.reset()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y() / 120.0
        if delta:
            self.camera.zoom(delta)
            self.update()

    def _drag_direction_move(self, dx: float, dy: float, entry: dict) -> Move | None:
        """Choose the face turn that best matches the drag direction."""
        drag_vec = np.array([dx, dy], dtype=float)
        drag_norm = np.linalg.norm(drag_vec)
        if drag_norm < 1e-6:
            return None
        drag_vec = drag_vec / drag_norm

        pos = entry.get("cubie_pos")
        cubie = self._state.cubie_at(pos) if pos is not None else None
        if cubie is None:
            home = entry.get("home")
            if home is not None:
                cubie = next((c for c in self._state.cubies.values() if c.home == home), None)
        if cubie is None:
            return None
        center = np.asarray(entry["world_center"], dtype=float)
        w, h = self.width(), self.height()

        best_move = None
        best_score = -1.0
        for face in ("U", "D", "L", "R", "F", "B"):
            axis = FACE_AXIS[face]
            layer = FACE_SIGN[face]
            if cubie.pos[axis] != layer:
                continue

            normal = np.array(FACE_NORMAL[face], dtype=float)
            for turns, sign in ((1, -1.0), (3, 1.0)):
                omega = sign * normal
                tangent = np.cross(omega, center)
                tnorm = np.linalg.norm(tangent)
                if tnorm < 1e-9:
                    continue
                tangent = tangent / tnorm
                p0 = center[None, :]
                p1 = (center + tangent * 0.45)[None, :]
                s0, _ = self.camera.project(p0, w, h)
                s1, _ = self.camera.project(p1, w, h)
                tvec = s1[0] - s0[0]
                tvec_norm = np.linalg.norm(tvec)
                if tvec_norm < 1e-6:
                    continue
                tvec = tvec / tvec_norm
                score = float(np.dot(tvec, drag_vec))
                if score > best_score:
                    best_score = score
                    best_move = Move(face, turns)
        if best_move is not None and best_score >= DRAG_MATCH_COS:
            return best_move
        return None


def _view_dir(eye: np.ndarray, points: np.ndarray) -> np.ndarray:
    centroid = points.mean(axis=0)
    v = eye - centroid
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])


def _path_from(poly: QPolygonF) -> QPainterPath:
    path = QPainterPath()
    path.addPolygon(poly)
    path.closeSubpath()
    return path
