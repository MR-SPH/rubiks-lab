@echo off
REM ============================================================
REM  RUBIK'S LAB - Windows build script (creates a standalone exe)
REM
REM  Requirements: Python 3.11+ installed and on PATH.
REM  Run from the project root:  build_windows.bat
REM ============================================================

echo [1/4] Creating an isolated build environment...
python -m venv .build-venv
call .build-venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo [3/4] Running the test suite...
python -m pytest tests -q
if errorlevel 1 (
    echo Tests failed - aborting the build.
    exit /b 1
)

echo [4/4] Building the executable...
pyinstaller --noconfirm --clean rubiks_lab.spec
if errorlevel 1 (
    echo PyInstaller failed - see the output above.
    exit /b 1
)

echo.
echo Done. The application is in dist\RubiksLab\RubiksLab.exe
echo You can copy the whole dist\RubiksLab folder anywhere.
pause
