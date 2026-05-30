"""
Central source of truth for application identity and on-disk data location.

Renaming the app (SunoSync -> Sunatra) must happen in exactly one place so the
appdirs data directory does not silently fork across modules. Historically the
data dir was referenced three different ways:

    appdirs.user_data_dir("SunoSync", "InternetThot")   # config, manifest, uuid cache
    appdirs.user_data_dir("SunoSync", "SunoSync")        # prompt vault (divergent!)

Both are migrated into the single canonical Sunatra dir by ``migrate_legacy_data``.
"""

import os
import shutil

import appdirs

APP_NAME = "Sunatra"
APP_AUTHOR = "twardoch"

# Public-facing identifiers reused across the UI, extensions, and services.
APP_ID = "sunatra.app"  # Windows AppUserModelID
GITHUB_OWNER = "twardoch"
GITHUB_REPO = "Sunatra"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_URL = f"{GITHUB_URL}/releases/latest"

# (name, author) pairs used by older builds. Order matters only for logging.
_LEGACY_DIRS = [
    ("SunoSync", "InternetThot"),
    ("SunoSync", "SunoSync"),
]


def user_data_dir() -> str:
    """Canonical per-user data directory for Sunatra. Created on demand."""
    path = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:  # pragma: no cover - extremely rare
        print(f"Could not create data dir {path}: {e}")
    return path


def data_path(filename: str) -> str:
    """Absolute path to *filename* inside the canonical data directory."""
    return os.path.join(user_data_dir(), filename)


def migrate_legacy_data() -> int:
    """One-shot, idempotent migration of legacy SunoSync data into the Sunatra
    data dir. Copies any file from a legacy dir that does not already exist in
    the new dir. Never deletes the legacy copies (safety net). Returns the count
    of files copied.
    """
    new_dir = user_data_dir()
    new_dir_norm = os.path.normcase(os.path.normpath(new_dir))
    copied = 0

    for name, author in _LEGACY_DIRS:
        try:
            legacy_dir = appdirs.user_data_dir(name, author)
        except Exception:
            continue
        if not legacy_dir or not os.path.isdir(legacy_dir):
            continue
        if os.path.normcase(os.path.normpath(legacy_dir)) == new_dir_norm:
            continue

        try:
            entries = os.listdir(legacy_dir)
        except OSError as e:
            print(f"Migration: cannot list {legacy_dir}: {e}")
            continue

        for entry in entries:
            src = os.path.join(legacy_dir, entry)
            dst = os.path.join(new_dir, entry)
            if not os.path.isfile(src) or os.path.exists(dst):
                continue
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as e:
                print(f"Migration: failed to copy {src} -> {dst}: {e}")

        if copied:
            print(f"Migration: imported {copied} file(s) from {legacy_dir} into {new_dir}")

    return copied
