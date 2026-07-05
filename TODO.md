# TODO

> **Progress — implementation iteration (done, validated):** Rebrand SunoSync→Sunatra
> across code/UI/extensions; centralized data dir + non-destructive legacy migration
> (`core/app_meta.py`); `pyproject.toml` + `hatch-vcs` semver-tag versioning (git-ignored
> `core/_version.py`); cross-platform `build.py` (validated: real `Sunatra.app` built on
> macOS); GitHub Actions CI (lint+compile+tests on Win/macOS/Linux + rebrand guard) and
> tag-triggered Release workflow; GitHub-Releases updater; pure unit-tested
> `song_passes_filters()` (issue #3); race regression test (issue #6); `TIT3` creation
> date (issue #2); hardened `sanitize_filename` (NFC/reserved); fixed two real bugs
> (`open_file` missing import; deferred-lambda `except e` NameError); `ruff` clean +
> **41 passing tests**. Remaining items below stay open.


> **Progress — uv tooling + package restructure (issue 103, done, validated):**
> Eliminated the root `main.py` — the app is now the importable `sunatra/` package
> (`python -m sunatra` / `sunatra` command). `uv build` produces a clean wheel+sdist;
> `build.py` rewritten (uv shebang: `uvx hatch clean` → `uv build` → PyInstaller);
> added `publish.py` (gitnextver → uv build → uv publish) and `install.py` (wheel →
> `uv tool install`). GitHub Actions migrated to uv end-to-end (+ optional `uv publish`
> job); added `uv.lock`. Real wheel and macOS `.app` both built. **45 tests pass, ruff
> clean.**

> **Progress — docs site + mypy (done, validated):** Added a Just-the-Docs `docs/` site
> (home, install, account setup, browser extension, library filters, build-from-source,
> FAQ) published to GitHub Pages; added a project icon at `docs/assets/icon.png`. Typed
> `song_passes_filters()` and cleared the last mypy error (`app.py` handler list) — `mypy
> sunatra` is clean across 33 modules and now runs in CI alongside ruff. **45 tests pass,
> ruff + mypy clean.**

Actionable plan for the **Sunatra** project (fork of `sunsetsacoustic/SunoSync`, now
`twardoch/Sunatra`). Items are grouped by source goal. Check off `- [ ]` as completed;
keep this file as the flat companion to `PLAN.md`.

Legend: `(bug)` defect fix · `(feat)` new capability · `(infra)` build/CI/tooling ·
`(refactor)` internal cleanup · `(sec)` security · `(verify)` confirm existing behavior.

---

## 1. Upstream issue triage (from github.com/sunsetsacoustic/SunoSync/issues)

> Decisions: We adopt the *valuable* asks below. We explicitly **reject** upstream
> issue #2's "Performance Optimization" #4 (forcing `existing_uuids = set()` to disable
> UUID pre-scan) — Sunatra already solves this better with the manifest
> (`core/manifest.py` `dedupe_set()`), which is faster *and* keeps dedupe correct.

### Issue #2 — Creation date + richer sidecar metadata `(feat)`
- [ ] Capture Suno `created_at` from the API response through `download_single_song()` into `embed_metadata()`.
- [x] Embed Suno creation date as ID3 `TIT3` (Subtitle), formatted `Suno Created: YYYY-MM-DD HH:MM:SS`, in `core/utils.py:embed_metadata()`.
- [ ] Optionally set the audio file's filesystem mtime to the Suno creation date via `os.utime()` (cross-platform). Treat creation-time (`ctime`) setting as Windows-only and guard it (see §3 cross-platform).
- [ ] Make the `.txt` sidecar (`save_metadata_to_file()` already exists) field-configurable: add Settings checkboxes for Title, Artist, Creation Date, UUID, Type, Model, Genre, BPM, Lyrics.
- [ ] Add a Settings toggle "Write .txt sidecar" (default off) and wire it through `configure()` like `save_lyrics`.

### Issue #3 — "Liked" filter not filtering `(bug)`
- [x] Audit the Liked filter path: both the API query param (`liked=true`, downloader.py ~L223) and the client-side `filter_liked_only` (~L461) reading `is_liked`/`reaction`. Determine which path is authoritative and whether they conflict.
- [x] Reproduce: scan with only "Liked" enabled and confirm non-liked tracks are excluded. Fix whichever layer leaks non-liked items.
- [x] Add a unit test feeding mocked feed JSON (liked + non-liked) through the filter and asserting only liked survive.

### Issue #6 — Same-title overwrite / threading race `(verify)` + `(feat)`
- [x] Confirm the TOCTOU race is closed: Sunatra already uses `reserve_unique_path()` (downloader.py ~L905) instead of the old check-then-write `get_unique_filename`. Add a regression test that runs concurrent writers targeting the same filename and asserts no overwrite.
- [ ] Expose download concurrency as a Setting (`max_workers`, currently hardcoded `3`), with `1` available for users on metered/unstable links; document the bandwidth-division tradeoff.

### Issue #5 — "doesn't work, program won't start" (vague, non-English) `(feat)`
- [ ] Improve first-run failure UX: when token is missing/invalid (401) or VLC is absent, show a clear, localized-friendly actionable message instead of a silent failure or generic crash.
- [ ] Surface a "Diagnostics" action (or log path hint) in the UI so users can self-report with `debug.log`.

### Issue #7 — Copilot audit (multi-part)
Most items map to §2–§4 below. Cross-references noted; the security items are listed here:
- [ ] `(sec)` Move the Suno `__client` token out of plaintext `config.json` into OS secure storage via `keyring` (Windows Credential Manager / macOS Keychain / Linux Secret Service). Store only a reference key in config. → also §4.
- [ ] `(sec)` Add an explicit "Sign out / Clear session" action that purges the token from secure storage and clears cached auth headers.
- [ ] `(sec)` Harden the token server (`services/token_server.py`): keep bind on `127.0.0.1`, but replace `Access-Control-Allow-Origin: *` with a per-session shared secret. App generates a random secret at startup, hands it to the extension (via a localStorage handshake or restricted-perms file), and rejects requests lacking it.
- [ ] `(sec)` Validate request `Origin`/method on the token server; reject GET-with-token and unexpected origins to prevent CSRF-style token pushes from arbitrary pages.
- [ ] `(sec)` Configure Sentry with `send_default_pii=False` and a `before_send` hook that redacts `cookie`, `authorization`, `token`, `__client`, prompts, and local paths. Add a Settings opt-out toggle and document what is/isn't sent. (Note: DSN is currently the `YOUR_DSN_HERE` placeholder — telemetry is off by default.)
- [ ] README clone path / releases / build-on-tag / dep pinning / layering / tests / linting → see §2, §3, §4.

---

## 2. Rebrand `SunoSync` → `Sunatra` (everywhere: code, UI, assets, identifiers)

> Scope: ~104 string hits across ~28 files. **Critical migration risk:** the appdirs
> data dir is keyed `appdirs.user_data_dir("SunoSync", "InternetThot")` in 3 core files —
> changing the name orphans every existing user's `config.json` + `library_manifest.json`.
> A one-shot data-dir migration is mandatory, not optional.

### 2.1 Identifiers, paths & data migration (do FIRST, carefully)
- [x] Decide canonical author string (replace `InternetThot`) for `appdirs.user_data_dir(...)`. Update all three call sites: `core/config_manager.py:16`, `core/manifest.py:34`, `core/utils.py:24`.
- [x] Add a one-shot, idempotent data-dir migration: on startup, if the new `Sunatra` data dir is empty but the legacy `SunoSync/InternetThot` dir exists, copy/move `config.json`, `library_manifest.json` (and `library_cache.json`/`tags.json` if applicable) over. Log the migration; never destroy the legacy copy on failure.
- [x] Update Windows AppUserModelID `myappid = 'sunosync.app.v2'` → `sunatra.app` (`main.py:142`).
- [x] Update Firefox extension gecko id `sunosync@sunsetsacoustic.dev` → a Sunatra id (`firefox_extension/manifest.json:8`).

### 2.2 Source code & window/UI strings
- [x] Replace `SunoSync` in window title and UI labels: `main.py` (`self.title("SunoSync")`), `ui/sidebar.py`, `ui/settings.py`, `ui/player.py`, `ui/vault.py`, `ui/layouts.py`.
- [x] Replace `SunoSync` references/comments/log strings in `core/*.py` and `services/*.py` (`token_server.py`, `discord.py`, `bug_reporter.py`).
- [x] Update Discord Rich Presence app/name strings in `services/discord.py` to "Sunatra".
- [x] Rename `class SunoSyncApp` → `SunatraApp` (and any `SunoSync`-named symbols) in `main.py`; update references.

### 2.3 Browser extensions (Chrome + Firefox, keep in sync)
- [x] Update extension `name`/`description`/branding in both `chrome_extension/manifest.json` and `firefox_extension/manifest.json` ("SunoSync Token Helper" → "Sunatra Token Helper").
- [x] Update `SunoSync` strings in `*/background.js`, `*/content.js`, `*/injected.js`, `*/popup.html`, `*/popup.js`.
- [ ] Regenerate/rename extension icons if they contain the old wordmark (`*/icons/`).

### 2.4 Build, packaging & release metadata
- [x] Rename `SunoSync.spec` → `Sunatra.spec` (or generate from `build.py`, see §3); update the PyInstaller `name=` and `icon=`, and the README build command.
- [x] Update `version.json` `download_url` (`sunsetsacoustic/SunoSyncV2` → `twardoch/Sunatra` releases). (Also see §3 — replace with git-tag/hatch-vcs flow.)
- [ ] Replace icons/splash assets carrying the SunoSync wordmark in `assets/` and `resources/` (e.g. `SunoSyncLogoIcon.png`, `splash.png`, `NewSplash.png`, `icon.ico`) with Sunatra branding; update `resource_path()` filenames.

### 2.5 Docs
- [x] Rewrite `README.md`: new name/tagline, correct clone path (`git clone https://github.com/twardoch/Sunatra.git && cd Sunatra` — fixes upstream #7 1.1), updated extension/build instructions, support links, author credit.
- [x] Update `CLAUDE.md` to reflect the new name (note the repo-dir/product-name now agree).
- [x] Grep-sweep for residual `SunoSync`/`SunoSyncV2`/`InternetThot`/`audioalchemy`/`sunsetsacoustic` and fix stragglers; add a CI grep-guard that fails if `SunoSync` reappears in tracked source (excluding CHANGELOG history).

---

## 3. Optimal refactor + easy cross-platform builds (Windows / macOS / Linux)

### 3.1 Packaging & versioning (hatch-vcs + semver git tags)
- [x] Add `pyproject.toml` using Hatchling + `hatch-vcs` as the build backend; set `dynamic = ["version"]` with `[tool.hatch.version] source = "vcs"`.
- [x] Configure `hatch-vcs` to write `src/sunatra/__version__.py` (or `core/__version__.py`); replace the hardcoded `core/version.py` (`__version__ = "3.0.0"`) with an import of the generated file (fallback to "0.0.0+unknown" when no tags).
- [x] Add the generated `__version__.py` to `.gitignore`.
- [ ] Tag the repo with an initial semver tag (e.g. `v3.1.0`) so `hatch-vcs` resolves a version; document the tag→release flow.
- [x] Move runtime deps from `requirements.txt` into `[project].dependencies` in `pyproject.toml`; keep `requirements.txt` generated/locked for reproducible CI.
- [x] Pin/lock dependencies (upstream #7 2.2): produce a locked set (`uv pip compile` or `pip-tools`) and use it in CI for deterministic builds.

### 3.2 Cross-platform correctness (remove Windows-only assumptions)
- [x] Audit and guard all `ctypes.windll` usage (`main.py` DPI awareness + taskbar appid; any `SetFileTime`) behind `sys.platform == "win32"`; provide no-op/alternate paths on macOS/Linux.
- [x] Audit `core/utils.py` and `services/bug_reporter.py` for Windows-specific calls (`os.startfile`, `windll`, message boxes); add macOS (`open`) / Linux (`xdg-open`) equivalents for `open_file()`.
- [ ] Provide platform icons: keep `.ico` for Windows, add `.icns` for macOS and PNG for Linux; select per-platform in the build.
- [ ] Document the VLC runtime dependency per OS (and detect-missing-VLC with a friendly message); consider bundling libVLC where licensing allows, or clearly instruct install.
- [ ] Verify `pynput` (media keys), `pypresence` (Discord), `customtkinter`, `Pillow` behave on all three OSes; gate any feature that can't (e.g. global media keys may need extra perms on macOS) with capability checks.

### 3.3 Build entry point
- [x] Add `build.py` (upstream #7 2.1) that derives all data-file paths from `pathlib.Path(__file__).parent`, validates they exist before building, and invokes PyInstaller — eliminating silent spec drift on refactors.
- [x] Make the spec/`build.py` parametric by platform (icon, binary name, `--windowed`, macOS `.app`/`BUNDLE`, Linux onefile).

### 3.4 GitHub Actions: build + release executables (robust & reliable)
- [x] Add `.github/workflows/ci.yml`: on push/PR, matrix over `{windows, macos, linux}` — install deps, `python -m compileall`, run lint + tests (headless, no GUI).
- [x] Add `.github/workflows/release.yml`: triggered on `v*` tags — matrix-build PyInstaller artifacts for Windows (`.exe`), macOS (`.app`/`.dmg` or zipped), Linux (onefile/AppImage), then create a GitHub Release and upload all assets. Establishes GitHub Releases as canonical binary source (fixes upstream #7 1.2).
- [x] Wire the in-app updater (`services/updater.py`) and `version.json`/release-check to read the latest GitHub Release of `twardoch/Sunatra` (replace the legacy Gist/permalink URL).
- [ ] Add build provenance: ensure each release artifact is traceable to its tag/commit; optionally attach checksums.
- [ ] (Optional) macOS code-signing/notarization and Windows signing slots in the workflow (documented as opt-in via secrets) to reduce AV false-positives noted in README.

### 3.5 Architecture & quality (upstream #7 §3, §6)
- [x] Move the package under `src/sunatra/` with a console/GUI entry point (`sunatra = "sunatra.main:main"`); make `main.py` a thin bootstrap that instantiates services and injects them into UI (reduce the 706-line orchestrator).
- [ ] Enforce one-way dependency direction `ui → services → core`; add `import-linter` contract checked in CI (catches circular imports / leaky abstractions).
- [x] Add `ruff` (lint+format) and `mypy` (gradual typing) configs; enforce in CI.
- [x] Stand up `tests/` with `pytest`: cover `sanitize_filename`/`reserve_unique_path`, manifest CRUD + migrations (`SCHEMA_VERSION`), filter logic, UUID extraction/embedding, and a headless core smoke test. Target ≥60% on `core/` first.
- [ ] Add a `library_cache.json` schema-version + migration path mirroring the manifest's `SCHEMA_VERSION` approach (upstream #7 5.1); back up + restart fresh on unmigratable data.
- [x] Harden `sanitize_filename()` (upstream #7 5.2): strip Windows-forbidden chars, NFC-normalize Unicode, enforce a safe length with a uniqueness-preserving hash suffix, and handle long-path limits.

---

## 4. App improvements: smarter, more customizable, more user-friendly

### 4.1 Reliability & networking
- [ ] Add bounded retries with exponential backoff + jitter for Suno API calls (`requests` in `core/downloader.py`); distinguish 401 (re-auth), 429 (rate-limit/backoff), and 5xx (retry) with clear UX per case.
- [ ] Add resumable/interruptible downloads: persist in-progress queue state so a crash or quit mid-batch resumes cleanly (the manifest already tracks completion).
- [ ] Centralize and tune the rate limiter; expose request delay + concurrency in Settings.

### 4.2 Intelligence & automation
- [ ] Smart auto-sync: optional background "watch for new tracks" that periodically scans the Suno feed and downloads new items automatically (respecting trashed set), with a notification.
- [ ] Auto-promotion rules: configurable rules to move Downloads → Library (e.g. auto-promote liked tracks, or after N days).
- [ ] Auto-tagging/organization: derive genre/BPM from prompt (helpers already exist in `utils.py`) and offer auto-foldering by genre/playlist/month/track in addition to current options.
- [ ] Duplicate/cleanup assistant: surface `manifest.find_duplicate_filepaths()` and "Forget Missing"/`prune_missing_at()` in a maintenance UI with one-click fixes.

### 4.3 Customization & UX
- [ ] Settings: configurable filename template (tokens like `{title}`, `{artist}`, `{date}`, `{uuid}`, `{model}`) instead of fixed naming.
- [ ] Settings: light/system theme option and accent color (currently hard-locked to Dark/blue in `main.py`).
- [ ] Add an onboarding/first-run wizard: choose Downloads + Library paths, connect token (extension or manual), verify VLC — addresses the "doesn't work" confusion (#5).
- [ ] In-app token health indicator (valid / expired / missing) with a one-click re-auth via the extension.
- [ ] Export/import library: export manifest + tags + prompt vault to a portable archive; import on a new machine.
- [ ] Optional localization scaffolding (i18n) given non-English users (#5); start with externalized UI strings.

### 4.4 Library, player & vault
- [ ] Player: gapless/queue improvements, persistent play queue across restarts, and keyboard shortcuts surfaced in UI.
- [ ] Library: faster virtualized grid for very large libraries (900+ tracks reported upstream); ensure scans stay off the UI thread.
- [ ] Prompt Vault: tags/search, and "send prompt back to Suno" deep-link/clipboard helper.
- [ ] Dashboard: richer stats (listening time, growth over time) sourced from the manifest + tags.

---

## Suggested execution order
1. **§3.1 + §3.5 scaffolding** (pyproject/hatch-vcs, src layout, tests, CI skeleton) — unblocks safe refactoring.
2. **§2.1 data-dir migration + rename** — high-risk, do behind tests early.
3. **§1 bug fixes** (#3 liked filter, #6 race regression test) + **§3.2 cross-platform guards**.
4. **§3.3/§3.4 build + release workflows** — ship Win/macOS/Linux binaries on tag.
5. **§1 features (#2) + §4 improvements** — iterate.
6. **§2 sweep + CI grep-guard**, docs, first `v*` release.
