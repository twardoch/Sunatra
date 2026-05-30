"""Ensure the repository root is importable so tests can ``import core`` etc.

Sunatra ships as top-level packages (core/, services/, ui/) plus main.py rather
than a src/ layout, so the repo root must be on sys.path for the test run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
