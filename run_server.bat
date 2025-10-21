@echo off
setlocal enabledelayedexpansion

set PORT=8000
set ENV_NAME=.venv

echo >>> Ensuring virtual environment: %ENV_NAME%
if not exist %ENV_NAME% (
    python -m venv %ENV_NAME%
)

echo >>> Activating venv
call %ENV_NAME%\Scripts\activate.bat

echo >>> Upgrading pip
python -m pip install --upgrade pip

echo >>> Installing requirements
pip install -r requirements.txt

:: OPTIONAL: set environment variables here (edit as needed)
:: set OPENAI_API_KEY=your-key-here

if not exist out mkdir out
if not exist bucket mkdir bucket
if not exist outputs mkdir outputs

echo >>> Starting Uvicorn on port %PORT% (Ctrl+C to stop)
uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload
