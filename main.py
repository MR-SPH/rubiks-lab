"""RUBIK'S LAB — 3D Rubik's Cube simulator & solver.

Run from the project root:

    python main.py
"""

from __future__ import annotations

import sys


def main() -> int:
    from pathlib import Path

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from ui.themes import apply_theme
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Rubik's Lab")
    app.setApplicationDisplayName("RUBIK'S LAB")
    app.setOrganizationName("Rubik's Lab")

    # Set application icon
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent

    icon_path = base_dir / "assets" / "icons" / "icon.png"
    if not icon_path.exists():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            icon_path = Path(meipass) / "assets" / "icons" / "icon.png"

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    apply_theme(app)

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
