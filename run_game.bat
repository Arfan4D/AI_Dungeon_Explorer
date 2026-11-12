@echo off
setlocal
cd /d "%~dp0"
set PY=
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY (
    py -%%V --version >nul 2>nul && set PY=py -%%V
  )
)
if not defined PY set PY=python
if not exist .venv (
  echo First run: setting things up...
  %PY% -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
python main.py
if errorlevel 1 pause
