#!/usr/bin/env python3
"""
Cross-platform build entry point for Sunatra.

Derives every data path from this file's location (no hard-coded spec to drift
out of sync — see upstream issue #7 §2.1), validates that referenced resources
exist, then invokes PyInstaller with platform-appropriate options:

    Windows : one-file  Sunatra.exe   (icon: resources/icon.ico)
    macOS   : Sunatra.app bundle       (icon: resources/icon.icns if present)
    Linux   : one-file  Sunatra        (no icon embedding)

Usage:
    python build.py            # build for the current OS
    python build.py --onedir   # force one-directory output (debugging)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "Sunatra"
ENTRY = ROOT / "main.py"

# (source, dest-in-bundle) data files/dirs to ship.
DATA = [
    ("assets", "assets"),
    ("resources", "resources"),
    ("version.json", "."),
]


def _validate() -> None:
    missing = [ENTRY.name] if not ENTRY.exists() else []
    for src, _ in DATA:
        if not (ROOT / src).exists():
            missing.append(src)
    if missing:
        print(f"ERROR: build inputs missing: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def _icon() -> str | None:
    if sys.platform == "win32":
        cand = ROOT / "resources" / "icon.ico"
    elif sys.platform == "darwin":
        cand = ROOT / "resources" / "icon.icns"
    else:
        return None
    return str(cand) if cand.exists() else None


def main() -> None:
    _validate()
    try:
        import PyInstaller.__main__  # noqa: WPS433
    except ImportError:
        print("ERROR: PyInstaller is not installed (pip install pyinstaller).", file=sys.stderr)
        sys.exit(1)

    onedir = "--onedir" in sys.argv

    args = [
        str(ENTRY),
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--collect-all", "customtkinter",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "babel.numbers",
    ]

    # One-file everywhere except macOS, where a .app bundle (onedir) is standard.
    if sys.platform == "darwin" or onedir:
        pass  # default is onedir
    else:
        args.append("--onefile")

    for src, dst in DATA:
        args += ["--add-data", f"{ROOT / src}{os.pathsep}{dst}"]

    icon = _icon()
    if icon:
        args += ["--icon", icon]

    print("Running: pyinstaller " + " ".join(args))
    PyInstaller.__main__.run(args)
    print(f"\nBuild complete. Artifacts in: {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
