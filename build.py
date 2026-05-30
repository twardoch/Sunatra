#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.10"
# ///
"""
Build Sunatra deliverables with uv + hatch + PyInstaller.

Two deliverables, both landing in ``dist/``:
  1. Python distribution — ``sunatra-X.Y.Z-py3-none-any.whl`` + sdist (``uv build``),
     for PyPI / ``uv tool install``. The version is stamped from the git tag by
     hatch-vcs.
  2. Standalone app — one-file ``Sunatra`` / ``Sunatra.exe`` on Windows/Linux and a
     ``Sunatra.app`` bundle on macOS (PyInstaller), for end users without Python.

Run directly (uv resolves its own environment):
    ./build.py              # clean + wheel/sdist + standalone executable
    ./build.py --wheel      # clean + wheel/sdist only (fast; used by publish/install)
    ./build.py --exe        # clean + standalone executable only

Importable too: ``from build import build_wheel, build_executable, clean``.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "Sunatra"
ENTRY = ROOT / "sunatra" / "__main__.py"

# (source relative to repo, destination inside the bundle) — matches resource_path().
DATA = [
    ("sunatra/assets", "assets"),
    ("sunatra/resources", "resources"),
]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def clean() -> None:
    """Remove previous build artifacts via hatch."""
    _run(["uvx", "hatch", "clean"])


def build_wheel() -> None:
    """Build the wheel + sdist into dist/ (version stamped from the git tag)."""
    _run(["uv", "build"])


def _icon() -> str | None:
    if sys.platform == "win32":
        cand = ROOT / "sunatra" / "resources" / "icon.ico"
    elif sys.platform == "darwin":
        cand = ROOT / "sunatra" / "resources" / "icon.icns"
    else:
        return None
    return str(cand) if cand.exists() else None


def build_executable() -> None:
    """Build the standalone app via PyInstaller, inside the project env (uv run)."""
    args = [
        "uv", "run", "--extra", "dev", "pyinstaller",
        str(ENTRY),
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--paths", str(ROOT),                 # so `import sunatra` resolves
        "--collect-all", "customtkinter",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "babel.numbers",
    ]
    # One-file everywhere except macOS, where a .app bundle (onedir) is standard.
    if sys.platform != "darwin":
        args.append("--onefile")
    for src, dst in DATA:
        args += ["--add-data", f"{ROOT / src}{os.pathsep}{dst}"]
    icon = _icon()
    if icon:
        args += ["--icon", icon]
    _run(args)


def build_all() -> None:
    clean()
    build_wheel()
    build_executable()


def main() -> None:
    if "--wheel" in sys.argv:
        clean()
        build_wheel()
    elif "--exe" in sys.argv:
        clean()
        build_executable()
    else:
        build_all()
    print(f"\nBuild complete. Artifacts in: {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
