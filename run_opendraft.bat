@echo off
REM Launches OpenDraft using the project's virtual environment.
REM Create a shortcut to this file for a desktop launcher.

set "APP_DIR=%~dp0"
set "PYTHONW=%APP_DIR%.venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo Could not find virtual environment at "%APP_DIR%.venv".
    echo Please create it first, e.g.:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

start "" "%PYTHONW%" "%APP_DIR%main.py"
