# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Sunatra** (formerly SunoSync) — a cross-platform desktop GUI app (Python + CustomTkinter) that bulk-downloads a user's Suno AI music library, manages it locally, and plays it back. It is an unofficial tool that talks to Suno's private `studio-api.prod.suno.com` API using the user's session cookie (`__client` token). Targets Windows, macOS, and Linux.

## Commands

Tooling is **uv**-based (uv manages Python; VLC required at runtime for audio).

```bash
uv sync --extra dev                 # create .venv with runtime + dev deps (pytest, ruff, mypy, pyinstaller)
uv run python -m sunatra            # run the app (there is NO root main.py)
uv run pytest                       # test suite (tests/, headless core logic)
uv run pytest tests/test_filters.py # single test file
uv run ruff check .                 # lint (config in pyproject.toml)
uv run python -m compileall sunatra build.py publish.py install.py   # syntax-check incl. GUI
./build.py                          # wheel + sdist (uv build) AND standalone app (PyInstaller) -> dist/
./build.py --wheel | --exe          # just one deliverable
./install.py                        # build wheel + `uv tool install` -> `sunatra` command
./publish.py                        # uvx gitnextver (bump+tag) -> uv build -> uv publish
```

The app is the package `sunatra/` (entry `sunatra/app.py:main`, run via `sunatra/__main__.py`). `debug.log`/`window_state.json` are written to CWD; bundled `assets/`, `resources/` live under `sunatra/` and are resolved by `resource_path()`.

### Versioning
Version comes from semver **git tags** via `hatch-vcs`. `uv build`/`uv sync` writes a git-ignored `sunatra/_version.py`; `sunatra/core/version.py` imports it with fallbacks. Cut a release by pushing a `vX.Y.Z` tag — `.github/workflows/release.yml` (uv + `build.py`) builds Win/macOS/Linux artifacts and attaches them to a GitHub Release; an optional job runs `uv publish` to PyPI when the `PUBLISH_TO_PYPI` repo var is set. `ci.yml` runs lint + compile + tests on all three OSes per push/PR, all via uv.

## Architecture

Single-process Tkinter app. `sunatra/app.py:SunatraApp` (a `ctk.CTk`) owns the window, builds all views into one `content_area`, and swaps them with `show_view()`. There is no router/MVC framework — views are long-lived widget instances stored in `self.views`, shown/hidden via `pack`. Cross-component communication uses **Tk virtual events** (`<<PlaySong>>`, `<<TagsUpdated>>`, `<<TrackChanged>>`) and a hand-rolled **`Signal`** observer (`sunatra/core/downloader.py`) for downloader→UI updates. Background work (downloads, token server, update check, media keys) runs on daemon threads; all UI mutation from threads is marshalled back with `self.after(...)`.

### Three layers
- **`sunatra/core/`** — non-UI logic. `downloader.py` (Suno API client + threaded download engine, `ThreadPoolExecutor`), `manifest.py` (the dedupe/state source of truth), `config_manager.py`, `utils.py` (UUID extraction, metadata embedding, filename sanitizing, file scanning), `theme.py`.
- **`sunatra/services/`** — background integrations: `token_server.py` (local HTTP listener for the browser extension), `updater.py` (GitHub release check), `media_keys.py` (`pynput` global hotkeys), `discord.py` (Rich Presence), `bug_reporter.py` (crash popup; Sentry).
- **`sunatra/ui/`** — one module per tab/widget (`downloader_tab`, `library`, `player`, `vault`, `dashboard`, `settings`, `downloads_tab`, `ignored_tab`, `sidebar`, `lyrics`, `widgets`, etc.). UI modules import from `core`/`services`, never the reverse.

### The manifest is the heart of dedupe (`sunatra/core/manifest.py`)
Every downloaded Suno track is identified by its **`SUNO_UUID`**, embedded as a `TXXX` ID3 tag (`sunatra/core/utils.py:embed_metadata` / `get_uuid_from_file`). `LibraryManifest` (`library_manifest.json` in the appdirs data dir) records every known UUID, its `filepath`, and `location` (`downloads` vs `library`), plus a separate `trashed` set of UUIDs permanently blocked from re-download. `dedupe_set()` = entries ∪ trashed is what the downloader skips. This replaced the old approach of re-walking the library and re-parsing ID3 tags every run (`get_downloaded_uuids`/`build_uuid_cache` in utils still exist as the legacy/fallback path). When editing download or library-move logic, keep the manifest authoritative — don't reintroduce disk-walk dedupe on the hot path.

The app models a **two-stage flow**: new tracks land in a **Downloads** folder (`downloads_path`), then get promoted to the **Library** folder (`library_path`). `sunatra/app.py:_run_path_migration()` is a one-shot, idempotent migration from the legacy single `path` config key to this split, bootstrapping the manifest by scanning the old library.

### Persistence & storage locations
- **App data dir** — resolved centrally via `sunatra/core/app_meta.py:user_data_dir()` (`appdirs.user_data_dir("Sunatra", "twardoch")`): `config.json` (via `ConfigManager`), `library_manifest.json`, `uuid_cache.json`, `prompts.json`. **Always go through `app_meta`** — never call `appdirs` directly (the old code forked into two divergent dirs). `app_meta.migrate_legacy_data()` (called once at startup from `main()` in `sunatra/app.py`) imports data from the legacy SunoSync dirs.
- **Writable mutable files** (`_data_base` in `sunatra/app.py`): next to the executable when frozen, else the data dir — `library_cache.json`, `tags.json`, `changelog.txt`. `window_state.json`/`debug.log` are written to CWD.
- Both `ConfigManager` and `LibraryManifest` **debounce writes** (0.5s timer) and quarantine corrupt JSON instead of crashing. On shutdown (`on_close`) they `flush()` pending writes — call `flush()` if you add a code path that must persist immediately.

### Browser extension auth (the "auto-token" feature)
`chrome_extension/` and `firefox_extension/` are near-identical MV3 extensions (Firefox manifest adds `browser_specific_settings.gecko`). The content/injected scripts grab the Suno `__client` cookie and POST it to the desktop app's `TokenServer` (`sunatra/services/token_server.py`, hardcoded `127.0.0.1:38945`, CORS-open). `sunatra/app.py:_on_extension_token` writes it into config and updates the Downloader tab. If you change the port or payload shape, update both extensions' `background.js`/`content.js` and `token_server.py` together.

### Suno API surface (`sunatra/core/downloader.py`)
All endpoints hang off `GEN_API_BASE = "https://studio-api.prod.suno.com"`: feed (`/api/feed/`, `/api/feed/v2`), workspaces/playlists (`/api/project/...`, `/api/playlist/...`), clip detail (`/api/clip/{id}`), WAV conversion (`/api/gen/{id}/convert_wav/`, `/api/gen/{id}/wav_file/`). Auth is `Authorization: Bearer <token>`. These are private/undocumented — verify behavior against live responses, expect breakage when Suno changes them.

## Conventions & gotchas
- **Cross-platform (Windows/macOS/Linux).** Windows-only calls (`ctypes.windll`, `SetCurrentProcessExplicitAppUserModelID`) are guarded behind `sys.platform == "win32"`; keep new platform-specific calls guarded. Frozen builds use `sys._MEIPASS`.
- **Audio engine is VLC** (`python-vlc`) — the app requires VLC installed system-wide; it is not bundled.
- A global `sys.excepthook` routes uncaught exceptions to Sentry + a crash popup. The Sentry DSN is a `"YOUR_DSN_HERE"` placeholder — telemetry is off until set; if enabled, `sunatra/services/telemetry.py:scrub_event` redacts token/cookie/secret values.
- The updater (`sunatra/services/updater.py`) checks the GitHub Releases API; `sunatra/core/version.py` holds `__version__` (from the git tag). There is no `version.json`.
- `resource_path()` in `sunatra/app.py` is the canonical way to locate bundled assets (`sunatra/assets`, `sunatra/resources`) in dev and frozen modes — use it, don't hardcode paths.
