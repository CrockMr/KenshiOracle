"""Locate optional research modules without importing Windows capture APIs."""
from pathlib import Path
import sys


def enable_research():
    folder = str(Path(__file__).resolve().parents[1] / 'tools/research')
    if folder not in sys.path:
        sys.path.insert(0, folder)
