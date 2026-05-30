# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Sunatra** (formerly SunoSync) — a cross-platform desktop GUI app (Python + CustomTkinter) that bulk-downloads a user's Suno AI music library, manages it locally, and plays it back. It is an unofficial tool that talks to Suno's private `studio-api.prod.suno.com` API using the user's session cookie (`__client` token). Targets Windows, macOS, and Linux.

## Commands

```bash
pip install -e .              # runtime deps (Python 3.10+; VLC required at runtime for audio)
python main.py                # run the app
pip install -e ".[dev]"       # + pytest, ruff, mypy, pyinstaller
pytest                        # run the test suite (tests/, ~41 tests, headless core logic)
pytest tests/test_filters.py  # run a single test file
ruff check .                  # lint (config in pyproject.toml)
python -m compileall core services ui main.py   # syntax-check incl. GUI (no display needed)
python build.py               # build a standalone executable -> dist/ (per-OS: .exe / .app / onefile)
```

`main.py` must be the working directory when run — it writes `debug.log`, `window_state.json`, and reads bundled `assets/`, `resources/`, `version.json` (the PyInstaller `--add-data` set in `build.py`).

### Versioning
Version comes from semver **git tags** via `hatch-vcs`. `build.py`/install writes a git-ignored `core/_version.py`; `core/version.py` imports it with fallbacks. Cut a release by pushing a `vX.Y.Z` tag — `.github/workflows/release.yml` builds Win/macOS/Linux artifacts and attaches them to a GitHub Release. `ci.yml` runs lint + compile + tests on all three OSes per push/PR.

## Architecture

Single-process Tkinter app. `main.py:SunatraApp` (a `ctk.CTk`) owns the window, builds all views into one `content_area`, and swaps them with `show_view()`. There is no router/MVC framework — views are long-lived widget instances stored in `self.views`, shown/hidden via `pack`. Cross-component communication uses **Tk virtual events** (`<<PlaySong>>`, `<<TagsUpdated>>`, `<<TrackChanged>>`) and a hand-rolled **`Signal`** observer (`core/downloader.py`) for downloader→UI updates. Background work (downloads, token server, update check, media keys) runs on daemon threads; all UI mutation from threads is marshalled back with `self.after(...)`.

### Three layers
- **`core/`** — non-UI logic. `downloader.py` (Suno API client + threaded download engine, `ThreadPoolExecutor`), `manifest.py` (the dedupe/state source of truth), `config_manager.py`, `utils.py` (UUID extraction, metadata embedding, filename sanitizing, file scanning), `theme.py`.
- **`services/`** — background integrations: `token_server.py` (local HTTP listener for the browser extension), `updater.py` (GitHub release check), `media_keys.py` (`pynput` global hotkeys), `discord.py` (Rich Presence), `bug_reporter.py` (crash popup; Sentry).
- **`ui/`** — one module per tab/widget (`downloader_tab`, `library`, `player`, `vault`, `dashboard`, `settings`, `downloads_tab`, `ignored_tab`, `sidebar`, `lyrics`, `widgets`, etc.). UI modules import from `core`/`services`, never the reverse.

### The manifest is the heart of dedupe (`core/manifest.py`)
Every downloaded Suno track is identified by its **`SUNO_UUID`**, embedded as a `TXXX` ID3 tag (`core/utils.py:embed_metadata` / `get_uuid_from_file`). `LibraryManifest` (`library_manifest.json` in the appdirs data dir) records every known UUID, its `filepath`, and `location` (`downloads` vs `library`), plus a separate `trashed` set of UUIDs permanently blocked from re-download. `dedupe_set()` = entries ∪ trashed is what the downloader skips. This replaced the old approach of re-walking the library and re-parsing ID3 tags every run (`get_downloaded_uuids`/`build_uuid_cache` in utils still exist as the legacy/fallback path). When editing download or library-move logic, keep the manifest authoritative — don't reintroduce disk-walk dedupe on the hot path.

The app models a **two-stage flow**: new tracks land in a **Downloads** folder (`downloads_path`), then get promoted to the **Library** folder (`library_path`). `main.py:_run_path_migration()` is a one-shot, idempotent migration from the legacy single `path` config key to this split, bootstrapping the manifest by scanning the old library.

### Persistence & storage locations
- **App data dir** — resolved centrally via `core/app_meta.py:user_data_dir()` (`appdirs.user_data_dir("Sunatra", "twardoch")`): `config.json` (via `ConfigManager`), `library_manifest.json`, `uuid_cache.json`, `prompts.json`. **Always go through `app_meta`** — never call `appdirs` directly (the old code forked into two divergent dirs). `app_meta.migrate_legacy_data()` (called once at startup from `main()`) imports data from the legacy SunoSync dirs.
- **Next to the executable / `main.py`** (`base_path`): `library_cache.json`, `tags.json`, `changelog.txt`, `window_state.json`, `debug.log`.
- Both `ConfigManager` and `LibraryManifest` **debounce writes** (0.5s timer) and quarantine corrupt JSON instead of crashing. On shutdown (`on_close`) they `flush()` pending writes — call `flush()` if you add a code path that must persist immediately.

### Browser extension auth (the "auto-token" feature)
`chrome_extension/` and `firefox_extension/` are near-identical MV3 extensions (Firefox manifest adds `browser_specific_settings.gecko`). The content/injected scripts grab the Suno `__client` cookie and POST it to the desktop app's `TokenServer` (`services/token_server.py`, hardcoded `127.0.0.1:38945`, CORS-open). `main.py:_on_extension_token` writes it into config and updates the Downloader tab. If you change the port or payload shape, update both extensions' `background.js`/`content.js` and `token_server.py` together.

### Suno API surface (`core/downloader.py`)
All endpoints hang off `GEN_API_BASE = "https://studio-api.prod.suno.com"`: feed (`/api/feed/`, `/api/feed/v2`), workspaces/playlists (`/api/project/...`, `/api/playlist/...`), clip detail (`/api/clip/{id}`), WAV conversion (`/api/gen/{id}/convert_wav/`, `/api/gen/{id}/wav_file/`). Auth is `Authorization: Bearer <token>`. These are private/undocumented — verify behavior against live responses, expect breakage when Suno changes them.

## Conventions & gotchas
- **Windows-targeted.** Expect `ctypes.windll`, `SetCurrentProcessExplicitAppUserModelID`, `.ico` icons, frozen-exe `sys._MEIPASS` handling. Guard new platform-specific calls in `try/except` like the existing code (it degrades silently off-Windows).
- **Audio engine is VLC** (`python-vlc`) — the app requires VLC installed system-wide; it is not bundled.
- A global `sys.excepthook` routes uncaught exceptions to Sentry + a crash popup. The Sentry DSN is a `"YOUR_DSN_HERE"` placeholder — telemetry is off until set.
- `version.json` (root) is the update-check manifest; `core/version.py` holds `__version__` used in-app.
- `resource_path()` in `main.py` is the canonical way to locate bundled assets in both dev and frozen modes — use it, don't hardcode paths.
