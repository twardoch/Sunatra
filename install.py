#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.10"
# ///
"""
Build Sunatra and install it locally on this machine.

Uses ``build.py`` to produce the wheel, then ``uv tool install`` to install it as
an isolated tool — this puts the ``sunatra`` command on PATH (run the app with
``sunatra``). The standalone PyInstaller bundle is not needed for a local install
when Python/uv is available.

Usage:
    ./install.py
"""

import glob
import subprocess
import sys
from pathlib import Path

import build  # sibling script module

ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    # 1. Build the wheel (clean first).
    build.clean()
    build.build_wheel()
    # 2. Install the freshly built wheel as a uv tool (creates the `sunatra` cmd).
    wheels = sorted(glob.glob(str(ROOT / "dist" / "*.whl")))
    if not wheels:
        print("No wheel found in dist/ after build.", file=sys.stderr)
        sys.exit(1)
    wheel = wheels[-1]
    _run(["uv", "tool", "install", "--force", wheel])
    print(f"\nInstalled {Path(wheel).name}. Launch the app with:  sunatra")


if __name__ == "__main__":
    main()
