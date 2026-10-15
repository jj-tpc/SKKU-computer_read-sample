@echo off
rem PPT Reader - Windows launcher. Double-click to run.
rem First run: creates .venv and installs requirements (internet needed once).
cd /d "%~dp0"

if exist ".venv\installed.ok" goto run

echo Setting up for the first run...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Python 3 is not installed. Install it from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package install failed. Check the internet connection and try again.
    pause
    exit /b 1
)
echo ok> ".venv\installed.ok"

:run
start "" ".venv\Scripts\pythonw.exe" main.py %*
