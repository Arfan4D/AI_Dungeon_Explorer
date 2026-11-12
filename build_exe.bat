@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   AI Dungeon Explorer - build a single .exe (Windows)
echo ============================================================

rem --- pick a Python version that Pygame supports
set PY=
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY (
    py -%%V --version >nul 2>nul && set PY=py -%%V
  )
)
if not defined PY set PY=python
%PY% --version
if errorlevel 1 (
  echo.
  echo Python was not found. Install Python 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH". Then run this file again.
  pause
  exit /b 1
)

if not exist .build-venv (
  echo Creating build environment...
  %PY% -m venv .build-venv
)
call .build-venv\Scripts\activate.bat

echo Installing Pygame and PyInstaller...
python -m pip install --upgrade pip
pip install "pygame>=2.5.2" pyinstaller
if errorlevel 1 (
  echo Could not install the packages. Check your internet connection.
  pause
  exit /b 1
)

echo Running the unit tests...
python -m unittest discover tests
if errorlevel 1 (
  echo Tests failed - stopping.
  pause
  exit /b 1
)

echo Building the .exe (this takes about a minute)...
pyinstaller --noconfirm --clean --onefile --noconsole --name AI_Dungeon_Explorer --icon assets\icon.ico main.py
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Try again without --noconsole to see error messages:
  echo   pyinstaller --onefile --name AI_Dungeon_Explorer main.py
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   Done!  Your game is:  dist\AI_Dungeon_Explorer.exe
echo   Copy that one file to any Windows PC - no Python needed.
echo   Results and screenshots are saved next to the .exe.
echo ============================================================
pause
