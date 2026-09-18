@echo off
cd /d "%~dp0"

set "VENV_DIR=.venv"

:: 1. Create venv if not exists
if not exist "%VENV_DIR%" (
    echo [SETUP] Setting up Python Virtual Environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python is installed and added to PATH.
        pause
        exit /b 1
    )
)

:: 2. Install dependencies
if exist "requirements.txt" (
    "%VENV_DIR%\Scripts\pip.exe" install -q --upgrade pip
    "%VENV_DIR%\Scripts\pip.exe" install -q -r requirements.txt
) else if exist "requirement.txt" (
    "%VENV_DIR%\Scripts\pip.exe" install -q --upgrade pip
    "%VENV_DIR%\Scripts\pip.exe" install -q -r requirement.txt
)

:: 3. Execute script
"%VENV_DIR%\Scripts\python.exe" universal_bulk.py
pause
