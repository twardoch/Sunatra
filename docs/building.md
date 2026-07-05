---
title: Build from source
layout: default
nav_order: 6
---

# Build from source

Sunatra is a proper Python package (`sunatra/`) built with [uv](https://docs.astral.sh/uv/).
There is no loose `main.py` — the app runs as `python -m sunatra`.

## Run it

```bash
git clone https://github.com/twardoch/Sunatra.git
cd Sunatra
uv run python -m sunatra      # syncs deps and launches
```

## Develop

```bash
uv sync --extra dev           # runtime + pytest, ruff, mypy, pyinstaller
uv run ruff check .           # lint
uv run mypy sunatra           # type-check
uv run pytest                 # tests (headless core logic)
uv run python -m compileall sunatra   # syntax-check incl. the GUI layer
```

CI runs lint, a syntax check, and the test suite on Windows, macOS, and Linux — all via
uv — for every push and pull request, plus a branding guard that fails if the legacy
`SunoSync` name reappears outside the migration code.

## Package executables

One build script produces both deliverables into `dist/`:

```bash
./build.py            # wheel + sdist (uv build) AND a standalone app (PyInstaller)
./build.py --wheel    # just the Python distribution
./build.py --exe      # just the standalone app
```

The standalone is a one-file binary on Windows and Linux, and a `.app` bundle on macOS.

## Install the `sunatra` command

```bash
./install.py          # build the wheel and install it as a uv tool
```

## Cut a release

Versions come from **semver git tags** via `hatch-vcs`; `sunatra/_version.py` is generated
at build time and never committed. Pushing a `vX.Y.Z` tag triggers the release workflow,
which builds executables for all three platforms and attaches them to a GitHub Release.

```bash
./publish.py          # uvx gitnextver (bump + tag) -> uv build -> uv publish
```

Publishing the wheel to PyPI is optional and off by default; enable it by setting the
`PUBLISH_TO_PYPI` repository variable and adding a PyPI token (or a Trusted Publisher).
GitHub Releases, not PyPI, are the primary way end users get Sunatra.
