# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) via git tags (`hatch-vcs`).

## [Unreleased] — Sunatra rebrand + cross-platform release pipeline

### Rebranded SunoSync → Sunatra
- Renamed the application, window title, classes (`SunoSyncApp` → `SunatraApp`),
  Discord Rich Presence, token server, crash dialog, log filenames, and both browser
  extensions (Chrome + Firefox, including manifest names and the Firefox gecko id).
- Centralized app identity in `core/app_meta.py` (`APP_NAME`, `APP_AUTHOR`, GitHub URLs,
  Windows AppUserModelID).
- **Data migration:** the per-user data directory moved to `Sunatra/twardoch`. A one-shot,
  idempotent, non-destructive migration imports config, manifest, prompt vault, and caches
  from the legacy `SunoSync/InternetThot` **and** `SunoSync/SunoSync` directories (the
  latter was a divergent location used only by the prompt vault — now unified).

### Packaging, versioning & CI/CD (cross-platform: Windows / macOS / Linux)
- Added `pyproject.toml` (Hatchling + `hatch-vcs`); the version is derived from semver git
  tags and written to a git-ignored `core/_version.py` at build time. `core/version.py`
  resolves it with safe fallbacks.
- Added `build.py`: a single cross-platform PyInstaller entry point that validates inputs,
  derives all paths from the repo (no more spec drift), and emits a one-file binary on
  Windows/Linux and a `.app` bundle on macOS. Removed the Windows-only `SunoSync.spec`.
- Added GitHub Actions: `ci.yml` (lint + syntax + tests on all three OSes, plus a
  rebrand-regression guard) and `release.yml` (tag-triggered builds + GitHub Release with
  per-OS artifacts). GitHub Releases are now the canonical binary source.
- Re-pointed the in-app updater (`services/updater.py`) at the GitHub Releases API with
  robust version parsing.

### Fixes
- **Bug:** `open_file` was called in `ui/library.py` but never imported (would raise
  `NameError` when opening a file/folder). Now imported.
- **Bug:** workspace/playlist fetch errors captured the `except ... as e` variable inside a
  deferred `self.after(...)` lambda; in Python 3 the variable is deleted at block end, so
  the error toast would raise `NameError`. Captured the message before deferring.
- **Liked filter (upstream #3):** extracted per-song filtering into a pure, unit-tested
  `song_passes_filters()` predicate (robust Liked detection across `is_liked`/reaction/vote)
  and removed the now-dead inline filter-flag block.
- **Race safety (upstream #6):** added a concurrency regression test confirming
  `reserve_unique_path()` (already used by the downloader) prevents same-name overwrites.
- Hardened `sanitize_filename()`: NFC Unicode normalization, Windows reserved-name handling,
  never-empty output (upstream #7 §5.2).
- Replaced deprecated `datetime.utcnow()` usage in the manifest.
- Guarded Windows-only `ctypes.windll` calls behind `sys.platform == "win32"`.
- **Security (upstream #7 §4.3):** Sentry now initializes with `send_default_pii=False`
  and a unit-tested `before_send` scrubber (`services/telemetry.py`) that redacts
  token/cookie/secret values from crash reports (defensive — telemetry is off by default).

### Added
- Embed the original Suno creation date as ID3 `TIT3` + a `SUNO_CREATED_AT` tag
  (upstream #2).
- Test suite (`tests/`, 41 tests) covering filters, filename safety, UUID round-trip,
  manifest CRUD/migration/quarantine, data-dir migration, and version parsing.
- Tooling config: `ruff` (lint) and `mypy` (typing) in `pyproject.toml`.

See `TODO.md` for the remaining roadmap (secure token storage, sidecar config, smart
auto-sync, theming, and more).
