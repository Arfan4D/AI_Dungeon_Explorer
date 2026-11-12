#!/usr/bin/env bash
# Build a single-file executable on macOS / Linux:  bash build_exe.sh
set -e
cd "$(dirname "$0")"
python3 -m venv .build-venv
source .build-venv/bin/activate
pip install --upgrade pip
pip install "pygame>=2.5.2" pyinstaller
python -m unittest discover tests
pyinstaller --noconfirm --clean --onefile --noconsole --name AI_Dungeon_Explorer main.py
echo "Done: dist/AI_Dungeon_Explorer"
