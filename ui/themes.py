"""Visual theme: palette, typography and the global QSS stylesheet.

Design language:
* deep charcoal/navy surfaces, hairline cool-grey borders;
* a single teal/cyan accent used sparingly for actions and highlights;
* generous paddings, 8-12 px radii, clear typographic hierarchy.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Palette tokens
# ---------------------------------------------------------------------------

BG_WINDOW = "#0b101d"        # deepest background
BG_PANEL = "#121a2b"         # sidebar / cards
BG_CARD = "#141d31"
BG_CARD_HOVER = "#1a2440"
BG_INPUT = "#0f1626"
BG_ELEVATED = "#1b2743"

BORDER = "#26314d"
BORDER_STRONG = "#38486f"

TEXT = "#e9eef7"
TEXT_MUTED = "#94a1ba"
TEXT_FAINT = "#5d6b88"

ACCENT = "#22d3ee"           # cyan accent
ACCENT_STRONG = "#2dd4bf"    # teal accent (primary actions)
ACCENT_DIM = "#155e6e"

SUCCESS = "#34d399"
WARNING = "#fbbf24"
DANGER = "#f87171"

FONT_STACK = '"Segoe UI", "Inter", "DejaVu Sans", "Helvetica Neue", sans-serif'
MONO_STACK = '"Consolas", "SF Mono", "DejaVu Sans Mono", monospace'

#: Move sticker colors used in the logo and the 2D net.
NET_COLORS = {
    "U": "#f3f6f9", "D": "#ffd503", "F": "#009c49",
    "B": "#0051ba", "R": "#ba1637", "L": "#ff600a",
}

QSS = f"""
* {{
    font-family: {FONT_STACK};
    outline: none;
}}
QMainWindow, QDialog {{
    background: {BG_WINDOW};
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
QToolTip {{
    background: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 6px 8px;
    border-radius: 6px;
}}

/* ---------- frames ---------- */
QFrame#card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#topbar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
QLabel#appTitle {{
    font-size: 17px;
    font-weight: 750;
    letter-spacing: 2.2px;
    color: {TEXT};
}}
QLabel#appSub {{
    font-size: 10.5px;
    color: {TEXT_FAINT};
    letter-spacing: 1.6px;
}}
QLabel#cardTitle {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.8px;
    color: {TEXT_MUTED};
}}
QLabel#muted {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#hint {{
    color: {TEXT_FAINT};
    font-size: 11.5px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
    font-weight: 600;
    font-size: 12.5px;
}}
QPushButton:hover {{
    background: #223054;
    border-color: #45598c;
}}
QPushButton:pressed {{
    background: #18233e;
}}
QPushButton:disabled {{
    background: #131b2c;
    border-color: {BORDER};
    color: {TEXT_FAINT};
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT_STRONG}, stop:1 #0ea795);
    border: none;
    color: #04231f;
    font-weight: 750;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #43e0cb, stop:1 #10b5a2);
}}
QPushButton#primary:pressed {{
    background: #0d9384;
}}
QPushButton#primary:disabled {{
    background: #1d3541;
    color: #4e6a70;
}}
QPushButton#danger {{
    background: transparent;
    border: 1px solid #5f2a33;
    color: {DANGER};
}}
QPushButton#danger:hover {{
    background: #2a151b;
    border-color: #7d3742;
}}
QPushButton#ghost {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}
QPushButton#ghost:hover {{
    color: {TEXT};
    border-color: {BORDER_STRONG};
    background: {BG_CARD_HOVER};
}}

/* move chips (U, U', U2 ...) */
QPushButton#moveBtn {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 4px;
    font-family: {MONO_STACK};
    font-weight: 700;
    font-size: 13px;
    color: #cfe6ef;
}}
QPushButton#moveBtn:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
    background: #10263a;
}}
QPushButton#moveBtn:pressed {{
    background: {ACCENT_DIM};
    color: #d9f6ff;
}}

/* segmented mode control */
QPushButton#segment {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px 16px;
    color: {TEXT_MUTED};
    font-weight: 600;
}}
QPushButton#segment:hover {{
    color: {TEXT};
    background: {BG_CARD_HOVER};
}}
QPushButton#segment:checked {{
    background: {BG_ELEVATED};
    color: {ACCENT};
    border: 1px solid {ACCENT_DIM};
}}

/* ---------- inputs ---------- */
QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT_DIM};
}}
QSpinBox:hover, QComboBox:hover {{
    border-color: {BORDER_STRONG};
}}
QSpinBox::up-button, QSpinBox::down-button, QComboBox::down-arrow {{
    border: none;
    background: transparent;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {ACCENT_DIM};
    color: {TEXT};
}}
QCheckBox {{
    spacing: 8px;
    color: {TEXT_MUTED};
}}
QCheckBox:hover {{ color: {TEXT}; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_STRONG};
    border-color: {ACCENT_STRONG};
}}

/* ---------- slider ---------- */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BG_INPUT};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_DIM};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    background: {ACCENT};
}}
QSlider::handle:horizontal:hover {{
    background: #7be7f6;
}}

/* ---------- progress ---------- */
QProgressBar {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_STRONG}, stop:1 {ACCENT});
    border-radius: 5px;
}}

/* ---------- tabs ---------- */
QTabWidget::pane {{
    border: none;
    top: 0px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_FAINT};
    padding: 7px 14px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
    font-weight: 650;
    font-size: 12px;
}}
QTabBar::tab:hover {{
    color: {TEXT_MUTED};
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

/* ---------- tables / lists ---------- */
QTableWidget, QListWidget {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_DIM};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER_STRONG};
    padding: 5px 8px;
    font-weight: 650;
}}

/* ---------- scrollbars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 9px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-width: 30px;
}}

/* ---------- status bar ---------- */
QStatusBar {{
    background: {BG_PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 11.5px;
}}
QStatusBar::item {{
    border: none;
}}

/* ---------- misc ---------- */
QSplitter::handle {{
    background: {BG_WINDOW};
    width: 3px;
}}
QLabel#timer {{
    font-family: {MONO_STACK};
    font-size: 31px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#timerRunning {{
    color: {ACCENT};
}}
QLabel#statValue {{
    font-family: {MONO_STACK};
    font-size: 17px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#statLabel {{
    font-size: 10px;
    letter-spacing: 1.2px;
    color: {TEXT_FAINT};
    font-weight: 650;
}}
QLabel#solutionText {{
    font-family: {MONO_STACK};
    font-size: 13.5px;
}}
QLabel#badge {{
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#badgeOk {{
    background: rgba(52, 211, 153, 0.14);
    color: {SUCCESS};
    border: 1px solid rgba(52, 211, 153, 0.4);
}}
QLabel#badgeInfo {{
    background: rgba(34, 211, 238, 0.12);
    color: {ACCENT};
    border: 1px solid rgba(34, 211, 238, 0.35);
}}
QLabel#badgeWarn {{
    background: rgba(251, 191, 36, 0.12);
    color: {WARNING};
    border: 1px solid rgba(251, 191, 36, 0.35);
}}
"""


def apply_theme(app: QApplication) -> None:
    """Install the dark palette and the stylesheet on the application."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG_WINDOW))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(BG_INPUT))
    palette.setColor(QPalette.AlternateBase, QColor(BG_CARD))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT_DIM))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT))
    palette.setColor(QPalette.ToolTipBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(TEXT_FAINT))
    app.setPalette(palette)
    app.setStyleSheet(QSS)
