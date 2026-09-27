@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHON_BIN="

if exist "%SCRIPT_DIR%..\venv\Scripts\python.exe" set "PYTHON_BIN=%SCRIPT_DIR%..\venv\Scripts\python.exe"
if not defined PYTHON_BIN (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_BIN=python"
)

if not defined PYTHON_BIN (
    echo Python was not found. Create a virtual environment and install requirements.txt first. 1>&2
    exit /b 1
)

"%PYTHON_BIN%" "%SCRIPT_DIR%dev.py" %*
exit /b %errorlevel%
