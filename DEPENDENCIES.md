# Dependencies

Runtime and development dependencies and why each is used. Declared in `pyproject.toml`
(runtime in `[project.dependencies]`, tooling in the `dev` optional group).

## Runtime

| Package | Why |
|---------|-----|
| `requests` | HTTP client for the Suno API and asset downloads. |
| `mutagen` | Read/write ID3 tags (title, artist, lyrics, cover art, `SUNO_UUID`, creation date). |
| `Pillow` | Image handling for cover art, icons, and the splash screen. |
| `customtkinter` | The dark-themed Tk-based GUI toolkit. |
| `python-vlc` | Audio playback engine (requires VLC installed on the system). |
| `pynput` | Global media-key hotkeys. |
| `pypresence` | Discord Rich Presence integration. |
| `pyperclip` | Clipboard access (copy prompts / file paths). |
| `colorama` | Cross-platform colored console output. |
| `appdirs` | Resolve the canonical per-user data directory. |
| `sentry-sdk` | Optional crash reporting (off by default; DSN is a placeholder). |

## Development / build

| Package | Why |
|---------|-----|
| `pytest`, `pytest-cov` | Test runner and coverage. |
| `ruff` | Linting and import sorting. |
| `mypy` | Static type checking. |
| `pyinstaller` | Build standalone executables (`build.py`). |
| `hatchling`, `hatch-vcs` | Build backend and git-tag-based versioning (build-system requires). |

## Build/dev tooling (invoked, not imported)

| Tool | Why |
|------|-----|
| `uv` | Environment, dependency resolution (`uv.lock`), `uv build`, `uv run`, `uv publish`, `uv tool install`. The primary dev/build driver. |
| `hatch` (`uvx hatch`) | `uvx hatch clean` in `build.py`. |
| `gitnextver` (`uvx gitnextver`) | Version bump + git tag in `publish.py`. |
| `PyInstaller` | Standalone executables (`build.py`). |

Helper scripts at the repo root (all run via the `uv run` shebang): `build.py`
(deliverables), `publish.py` (PyPI), `install.py` (local `sunatra` command).

## System

- **VLC media player** — required at runtime for audio playback (not bundled).
- **Tcl/Tk** — required for the GUI; bundled with standard Python installers and CI Python.
- **uv** — install from <https://docs.astral.sh/uv/>; manages Python itself.
