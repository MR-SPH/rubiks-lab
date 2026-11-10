@echo off
cd /d "%~dp0"
title Rubiks Lab Launcher

echo ========================================================
echo        RUBIK'S LAB - 3D Cube Simulator and Solver
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" goto check_pyside

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed or not in PATH!
        echo Please install Python 3.11+ from https://www.python.org/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
    set PY_EXE=py
) else (
    set PY_EXE=python
)

echo [1/2] Creating virtual environment...
%PY_EXE% -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/2] Installing dependencies...
.\.venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
goto launch

:check_pyside
.\.venv\Scripts\python.exe -c "import PySide6" >nul 2>nul
if %errorlevel% neq 0 (
    echo Installing missing dependencies...
    .\.venv\Scripts\pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:launch
echo Starting RUBIK'S LAB...
.\.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
