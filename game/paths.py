"""Where the game reads and writes files.

When the game is packaged with PyInstaller (a single .exe) the code lives in a
temporary folder, so results / screenshots must go next to the .exe instead.
"""
import os
import sys


def app_dir() -> str:
    if getattr(sys, "frozen", False):                     # running as a packaged .exe
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
