@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NutriFood-Health

echo ========================================
echo       NutriFood-Health - Starting
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo Python 3 is required but was not found.
        echo Install Python 3.10+ with "Add Python to PATH", then run this file again.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating local virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo [2/3] Installing/updating required libraries...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo pip update failed. Continuing...
)
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Library installation failed. Check internet access and try again.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
    )
)

echo [3/3] Starting NutriFood-Health...
echo.
start "NutriFood-Health Browser" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
"%VENV_PY%" app.py

if errorlevel 1 (
    echo.
    echo NutriFood-Health stopped because of an error.
    pause
)
endlocal
