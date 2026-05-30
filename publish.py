#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.10"
# ///
"""
Publish Sunatra to PyPI.

Flow (order matters — the version must be tagged *before* the wheel is built so
hatch-vcs stamps the right version into the artifact):

  1. ``uvx gitnextver`` — compute the next semantic version from git history and
     create + push the ``vX.Y.Z`` tag.
  2. ``build.py`` (``clean`` + ``build_wheel``) — build the wheel + sdist at the
     freshly tagged version.
  3. ``uv publish`` — upload ``dist/*`` to PyPI (credentials from
     ``UV_PUBLISH_TOKEN`` / ``~/.pypirc``).

Usage:
    ./publish.py            # auto-bump (gitnextver default)
    ./publish.py patch      # pass-through args go to gitnextver
"""

import subprocess
import sys
from pathlib import Path

import build  # sibling script module

ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    # 1. Bump + tag the release.
    gitnextver_args = sys.argv[1:] or ["."]
    _run(["uvx", "gitnextver", *gitnextver_args])
    # 2. Build the Python distribution at the new version.
    build.clean()
    build.build_wheel()
    # 3. Upload to PyPI.
    _run(["uv", "publish"])
    print("\nPublished to PyPI.")


if __name__ == "__main__":
    main()
