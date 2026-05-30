# Sunatra

**Your World, Your Music. Seamlessly Synced.**

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

Requires **Python 3.10+**, **git**, and **VLC**.

```bash
git clone https://github.com/twardoch/Sunatra.git
cd Sunatra
pip install -e .          # installs runtime dependencies
python main.py            # run the app
```

## Build an executable

A single cross-platform build script handles Windows, macOS, and Linux:

```bash
pip install -e ".[dev]"   # includes PyInstaller
python build.py           # output in dist/
```

`build.py` derives all paths from the repo, validates inputs, and produces a one-file
binary on Windows/Linux and a `.app` bundle on macOS.

## Versioning & releases

Sunatra uses **semantic-version git tags** via `hatch-vcs`. The running version is
derived from the latest tag (`core/_version.py` is generated at build time and is not
committed). Pushing a `vX.Y.Z` tag triggers the GitHub Actions release workflow, which
builds executables for all three platforms and attaches them to a GitHub Release.

```bash
git tag v3.1.0 && git push origin v3.1.0    # cuts a release
```

## Development

```bash
pip install -e ".[dev]"
ruff check .                       # lint
pytest                             # tests
python -m compileall core services ui main.py
```

CI runs lint, a syntax check, and the test suite on Windows, macOS, and Linux for every
push and pull request.

## License

See [LICENSE](LICENSE). Created by the Sunatra contributors; originally based on SunoSync
by @InternetThot. Sunatra is unofficial and not affiliated with Suno AI.
