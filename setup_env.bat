@echo off
REM ============================================================
REM AI Design Engineer - Windows Setup Script
REM ------------------------------------------------------------
REM This script creates a virtual environment (.venv),
REM activates it, and installs all requirements.
REM Run this once before using the system.
REM ============================================================

SET VENV_DIR=.venv

IF NOT EXIST %VENV_DIR% (
    echo Creating virtual environment in %VENV_DIR% ...
    python -m venv %VENV_DIR%
)

echo Activating virtual environment...
CALL %VENV_DIR%\Scripts\activate

echo Installing requirements...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ============================================================
echo Virtual environment ready!
echo To activate later, run:
echo    %VENV_DIR%\Scripts\activate
echo Then start the app with:
echo    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo ============================================================
