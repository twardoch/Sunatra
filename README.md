# Sunatra

**Your World, Your Music. Seamlessly Synced.**

[![CI](https://github.com/twardoch/Sunatra/actions/workflows/ci.yml/badge.svg)](https://github.com/twardoch/Sunatra/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/twardoch/Sunatra?sort=semver)](https://github.com/twardoch/Sunatra/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Sunatra is a cross-platform desktop app for your [Suno](https://suno.com) AI music
library: a bulk downloader, a rich music library with playback, a prompt vault, and
companion browser extensions for one-click authentication — in one application.

> Sunatra is the actively maintained successor to *SunoSync*. It is an unofficial tool
> and is not affiliated with Suno AI.

## Features

- **Smart downloader** — bulk-download your whole Suno library; filter by Liked, Public,
  Trash, Uploads, Covers, Personas and more; choose **MP3** or lossless **WAV**.
- **Metadata embedding** — Title, Artist, Lyrics, Cover Art, the Suno `UUID`, and the
  original **Suno creation date** are written into the audio tags.
- **Music library** — dark-themed browser with clean titles, Like/Star/Trash tagging,
  and a stats dashboard.
- **Two-stage flow** — new tracks land in a **Downloads** folder, then get promoted to
  your **Library**. A manifest tracks every UUID so re-runs only fetch what's new.
- **Prompt vault** — save and one-click-copy your best prompts.
- **Browser extensions** — Chrome and Firefox companions auto-sync your Suno session
  token to the app (no manual cookie copying).

## Install

Pre-built executables for **Windows, macOS, and Linux** are published on the
[Releases page](https://github.com/twardoch/Sunatra/releases/latest).

| OS | Download | Notes |
|----|----------|-------|
| Windows | `Sunatra-windows.zip` → `Sunatra.exe` | Some antivirus may flag unsigned indie builds. |
| macOS | `Sunatra-macos.zip` → `Sunatra.app` | Right-click → Open the first time (unsigned). |
| Linux | `Sunatra-linux.zip` → `Sunatra` | `chmod +x Sunatra` then run. |

**Audio engine:** Sunatra plays audio through [VLC](https://www.videolan.org/), which
must be installed on your system (it is not bundled).

## Connect your Suno account

- **Easy (recommended):** install the Sunatra browser extension (see below). It detects
  when Sunatra is running and syncs your session token automatically.
- **Manual:** in the app click *Get Token*, log in to suno.com, open DevTools →
  Application → Cookies, and copy the `__client` cookie.

### Browser extension

**Chrome / Edge / Chromium:** `chrome://extensions/` → enable Developer Mode →
*Load unpacked* → select the `chrome_extension/` folder.

**Firefox (121+):** `about:debugging#/runtime/this-firefox` → *Load Temporary Add-on* →
select `firefox_extension/manifest.json`. (Temporary add-ons are removed when Firefox
closes; a signed build is planned.)

## Run from source

Requires [**uv**](https://docs.astral.sh/uv/), **git**, and **VLC** (Python is managed
by uv).

```bash
git clone https://github.com/twardoch/Sunatra.git
cd Sunatra
uv run python -m sunatra      # syncs deps and launches the app
```

Sunatra is a proper Python package (`sunatra/`) — there is no loose `main.py`. The app
runs as `python -m sunatra`, or as the `sunatra` command once installed.

## Install locally

```bash
./install.py        # builds the wheel and installs it as a uv tool -> `sunatra` command
```

## Build executables

A single uv-driven build script produces both deliverables into `dist/`:

```bash
./build.py            # wheel + sdist (uv build) AND a standalone app (PyInstaller)
./build.py --wheel    # just the Python distribution
./build.py --exe      # just the standalone app
```

The standalone is a one-file binary on Windows/Linux and a `.app` bundle on macOS.

## Versioning & releases

Sunatra uses **semantic-version git tags** via `hatch-vcs`; the running version is derived
from the latest tag (`sunatra/_version.py` is generated at build time and is not
committed). Pushing a `vX.Y.Z` tag triggers the GitHub Actions release workflow, which
builds executables for all three platforms and attaches them to a GitHub Release.

```bash
./publish.py        # uvx gitnextver (bump+tag) -> uv build -> uv publish (PyPI)
```

## Development

```bash
uv sync --extra dev
uv run ruff check .                 # lint
uv run pytest                       # tests
uv run python -m compileall sunatra
```

CI runs lint, a syntax check, and the test suite on Windows, macOS, and Linux (all via uv)
for every push and pull request.

### Project layout

```text
sunatra/                  # the application package — run: python -m sunatra
├── app.py                #   SunatraApp + main() entry point
├── core/                 #   downloader, manifest (dedupe), config, utils, app identity
├── services/             #   token server, updater, media keys, Discord, telemetry
├── ui/                   #   CustomTkinter tabs and widgets
└── assets/  resources/   #   bundled icons & splash (package data)
build.py                  # build wheel/sdist + standalone app (uv + PyInstaller)
publish.py                # bump tag + build + uv publish to PyPI
install.py                # build wheel + uv tool install (the `sunatra` command)
chrome_extension/  firefox_extension/   # companion MV3 token-sync extensions
tests/                    # pytest suite
```

## License

See [LICENSE](LICENSE). Created by the Sunatra contributors; originally based on SunoSync
by @InternetThot. Sunatra is unofficial and not affiliated with Suno AI.
