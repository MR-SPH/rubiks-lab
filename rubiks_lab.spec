# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RUBIK'S LAB (Windows, one-folder build).

Usage (from the project root, on Windows):

    pip install pyinstaller
    pyinstaller --noconfirm rubiks_lab.spec

The result lands in dist/RubiksLab/ as RubiksLab.exe together with the
runtime folder.  A one-folder build is recommended over one-file: it
starts instantly and avoids antivirus false positives.
"""

import os

block_cipher = None

HERE = os.path.abspath(".")

from PyInstaller.utils.hooks import collect_all  # noqa: E402

# Bundle the kociemba package completely: its native C extension needs
# cffi's _cffi_backend and the package ships runtime data files.
koc_datas, koc_binaries, koc_hidden = collect_all("kociemba")
koc_hidden += ["_cffi_backend", "cffi"]

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=koc_binaries,
    datas=[
        # bundle the icon; screenshots/docs are not needed inside the exe
        (os.path.join("assets", "icons", "icon.ico"), "assets/icons"),
        (os.path.join("assets", "icons", "icon.png"), "assets/icons"),
    ] + koc_datas,
    hiddenimports=[
        # Qt plugins are picked up automatically; be explicit about the
        # offscreen/legacy fallbacks some Windows systems need.
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ] + koc_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "pytest",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RubiksLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # windowed app: no console window
    icon=os.path.join("assets", "icons", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="RubiksLab",
)
