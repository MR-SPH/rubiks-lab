"""Reusable UI building blocks: cards, logo, chips, the 2D cube net."""

from __future__ import annotations

import html

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .themes import ACCENT, NET_COLORS, TEXT_FAINT, TEXT_MUTED


class Card(QFrame):
    """A rounded panel with an optional small-caps title."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(10)
        if title:
            lbl = QLabel(title.upper())
            lbl.setObjectName("cardTitle")
            self._layout.addWidget(lbl)

    def body(self) -> QVBoxLayout:
        return self._layout


class LogoMark(QWidget):
    """Small isometric cube glyph painted with the six face colors."""

    def __init__(self, size: int = 30, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        s = self._size
        cx, cy = s * 0.5, s * 0.52
        r = s * 0.36  # hexagon radius
        # isometric cube: hexagon split into three rhombi
        top = QPointF(cx, cy - r)
        ur = QPointF(cx + r * 0.87, cy - r * 0.5)
        lr = QPointF(cx + r * 0.87, cy + r * 0.5)
        bottom = QPointF(cx, cy + r)
        ll = QPointF(cx - r * 0.87, cy + r * 0.5)
        ul = QPointF(cx - r * 0.87, cy - r * 0.5)
        center = QPointF(cx, cy)
        faces = [
            (QPolygonF([top, ur, center, ul]), NET_COLORS["U"]),
            (QPolygonF([center, ur, lr, bottom]), NET_COLORS["R"]),
            (QPolygonF([ul, center, bottom, ll]), NET_COLORS["F"]),
        ]
        pen = QPen(QColor("#0b101d"), max(1.0, s * 0.045))
        for poly, color in faces:
            painter.setPen(pen)
            painter.setBrush(QColor(color))
            painter.drawPolygon(poly)
        painter.end()


class ModeSwitch(QWidget):
    """Segmented control for the three application modes."""

    modeSwitched = Signal(str)

    def __init__(self, modes: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QButtonGroup, QPushButton

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in modes:
            btn = QPushButton(label)
            btn.setObjectName("segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.modeSwitched.emit(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            layout.addWidget(btn)
        self._buttons[modes[0][0]].setChecked(True)

    def switched_signal(self):
        return self.modeSwitched

    def button(self, key: str):
        return self._buttons[key]

    def set_current(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    @property
    def current(self) -> str:
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return ""


def chips_html(moves, current: int = -1, dim_done: bool = True,
               chip_px: int = 13) -> str:
    """Render a move sequence as colored HTML chips (wrapping friendly)."""
    out = []
    for i, move in enumerate(moves):
        text = html.escape(str(move))
        if i == current:
            style = (
                f"background:{ACCENT}; color:#06222a; font-weight:800;"
                f"border-radius:4px; padding:1px 5px; font-size:{chip_px}px"
            )
        elif dim_done and current >= 0 and i < current:
            style = (
                f"background:#1a2440; color:#55617c;"
                f"border-radius:4px; padding:1px 5px; font-size:{chip_px}px"
            )
        else:
            style = (
                "background:#18223a; color:#c9e7f2;"
                f"border-radius:4px; padding:1px 5px; font-size:{chip_px}px"
            )
        out.append(f'<span style="{style}">&nbsp;{text}&nbsp;</span>')
    return "&nbsp;".join(out)


class StatTile(QWidget):
    """Small label-over-value tile used in the stats and info panels."""

    def __init__(self, label: str, value: str = "--", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._label = QLabel(label.upper())
        self._label.setObjectName("statLabel")
        self._value = QLabel(value)
        self._value.setObjectName("statValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class Badge(QLabel):
    """Pill-shaped status badge (Solved / Scrambled / ...)."""

    def __init__(self, text: str = "", kind: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        self.setObjectName(f"badge{'Ok' if kind == 'ok' else 'Warn' if kind == 'warn' else 'Info'}")

    def set_text(self, text: str, kind: str | None = None) -> None:
        if kind:
            self.set_kind(kind)
        self.setText(text)
        self.setVisible(bool(text))


class CubeNet(QWidget):
    """2D unfolded cube net (a compact, always-correct state readout).

        .   U   .   .
        L   F   R   B
        .   D   .   .
    """

    CELL = 14
    GAP = 2
    FACE_GAP = 4
    MARGIN = 3

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        face_w = 3 * self.CELL + 2 * self.GAP
        w = 2 * self.MARGIN + 4 * face_w + 3 * self.FACE_GAP
        h = 2 * self.MARGIN + 3 * face_w + 2 * self.FACE_GAP
        self.setMinimumSize(w, h)
        self.setFixedSize(w, h)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            facelets = self._state.facelets()
        except Exception:
            painter.end()
            return
        c, g = self.CELL, self.GAP
        face_size = 3 * c + 2 * g
        m, fg = self.MARGIN, self.FACE_GAP
        layout = {
            "U": (1, 0), "L": (0, 1), "F": (1, 1),
            "R": (2, 1), "B": (3, 1), "D": (1, 2),
        }
        for face, (col, row) in layout.items():
            origin_x = m + col * (face_size + fg)
            origin_y = m + row * (face_size + fg)
            for i, color in enumerate(facelets[face]):
                r, cc = divmod(i, 3)
                x = origin_x + cc * (c + g)
                y = origin_y + r * (c + g)
                painter.setPen(QPen(QColor("#0b101d"), 1))
                painter.setBrush(QColor(NET_COLORS.get(color, "#333")))
                painter.drawRoundedRect(QRectF(x, y, c, c), 2.5, 2.5)
        painter.end()
