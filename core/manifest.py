"""
Library manifest — single source of truth for which Suno UUIDs Sunatra has
downloaded, where each file currently lives (Downloads vs Library), and which
UUIDs the user has explicitly trashed (permanent dismiss; survives entry removal).

Replaces the previous disk-walk dedupe (`get_downloaded_uuids` /
`build_uuid_cache`) so the downloader does not have to re-read ID3 tags from
the library on every run.

On-disk file: ``<user_data_dir>/library_manifest.json``
"""

import datetime
import json
import os
import threading
import time

from core.app_meta import user_data_dir

SCHEMA_VERSION = 1

# Match ConfigManager's debounce window — same rationale (rapid set() bursts
# from UI traces should coalesce into one disk write).
_SAVE_DEBOUNCE_SECONDS = 0.5

LOCATION_DOWNLOADS = "downloads"
LOCATION_LIBRARY = "library"


def _utcnow_iso() -> str:
    """UTC timestamp as ``YYYY-MM-DDTHH:MM:SSZ`` (tz-aware; avoids the
    deprecated ``datetime.utcnow``)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_manifest_path() -> str:
    return os.path.join(user_data_dir(), "library_manifest.json")


class LibraryManifest:
    def __init__(self, path: str | None = None):
        self.path = path or default_manifest_path()
        self.entries: dict[str, dict] = {}
        # trashed is now a dict {uuid: {title, artist, trashed_at}} so the
        # Ignored tab can show useful info instead of opaque UUIDs. Older
        # manifests stored a list of UUIDs only; load() normalises both.
        self.trashed: dict[str, dict] = {}
        self._save_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self.load()

    # --- Persistence ---------------------------------------------------------

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.entries = {}
            self.trashed = {}
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            quarantine = f"{self.path}.corrupt-{int(time.time())}"
            try:
                os.replace(self.path, quarantine)
                print(f"Manifest was corrupt; moved to {quarantine}: {e}")
            except OSError as move_err:
                print(f"Manifest corrupt and could not be quarantined: {move_err}")
            self.entries = {}
            self.trashed = {}
            return
        except OSError as e:
            print(f"Error reading manifest: {e}")
            self.entries = {}
            self.trashed = {}
            return

        if not isinstance(data, dict):
            self.entries = {}
            self.trashed = {}
            return
        entries = data.get("entries", {})
        trashed = data.get("trashed", {})
        self.entries = entries if isinstance(entries, dict) else {}
        # Migration: older manifests stored trashed as a flat list of UUIDs.
        if isinstance(trashed, list):
            self.trashed = {u: {} for u in trashed if isinstance(u, str)}
        elif isinstance(trashed, dict):
            self.trashed = trashed
        else:
            self.trashed = {}

    def save(self) -> None:
        # Cancel any pending debounced save — we're writing now.
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
            payload = {
                "version": SCHEMA_VERSION,
                "entries": dict(self.entries),
                "trashed": dict(self.trashed),
            }
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as e:
            print(f"Error saving manifest: {e}")

    def _schedule_save(self) -> None:
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            timer = threading.Timer(_SAVE_DEBOUNCE_SECONDS, self.save)
            timer.daemon = True
            self._save_timer = timer
            timer.start()

    def flush(self) -> None:
        """Force any pending debounced save to disk now."""
        with self._lock:
            timer = self._save_timer
            self._save_timer = None
        if timer is not None:
            timer.cancel()
        self.save()

    # --- Entry CRUD ----------------------------------------------------------

    def add(self, uuid: str, *, title: str = "", artist: str = "",
            filepath: str = "", location: str = LOCATION_DOWNLOADS) -> None:
        if not uuid:
            return
        with self._lock:
            self.entries[uuid] = {
                "title": title,
                "artist": artist,
                "filepath": filepath,
                "location": location,
                "downloaded_at": _utcnow_iso(),
            }
        self._schedule_save()

    def get(self, uuid: str) -> dict | None:
        return self.entries.get(uuid)

    def remove(self, uuid: str) -> None:
        with self._lock:
            self.entries.pop(uuid, None)
        self._schedule_save()

    def move(self, uuid: str, new_filepath: str, new_location: str) -> None:
        """Update an existing entry's filepath/location (for Downloads -> Library)."""
        with self._lock:
            entry = self.entries.get(uuid)
            if entry is None:
                return
            entry["filepath"] = new_filepath
            entry["location"] = new_location
        self._schedule_save()

    def trash(self, uuid: str, *, title: str = "", artist: str = "") -> None:
        """Add UUID to trashed set and remove its entry. Trashed UUIDs are
        permanently blocked from re-download. If title/artist aren't supplied,
        they're inherited from the existing entry (if any)."""
        if not uuid:
            return
        with self._lock:
            existing = self.entries.pop(uuid, None) or {}
            self.trashed[uuid] = {
                "title": title or existing.get("title", ""),
                "artist": artist or existing.get("artist", ""),
                "trashed_at": _utcnow_iso(),
            }
        self._schedule_save()

    def untrash(self, uuid: str) -> None:
        """Remove a UUID from the trashed set. Does NOT re-create its entry —
        the next download run can fetch it normally."""
        with self._lock:
            self.trashed.pop(uuid, None)
        self._schedule_save()

    # --- Queries -------------------------------------------------------------

    def dedupe_set(self) -> set[str]:
        """UUIDs that should be skipped on the next download run."""
        with self._lock:
            return set(self.entries.keys()) | set(self.trashed.keys())

    def by_location(self, location: str) -> list[dict]:
        """Snapshot of entries at *location*, each augmented with its uuid."""
        with self._lock:
            return [
                {**entry, "uuid": uuid}
                for uuid, entry in self.entries.items()
                if entry.get("location") == location
            ]

    def all_entries(self) -> list[dict]:
        with self._lock:
            return [{**entry, "uuid": uuid} for uuid, entry in self.entries.items()]

    def trashed_entries(self) -> list[dict]:
        """Snapshot of trashed entries as {uuid, title, artist, trashed_at} dicts."""
        with self._lock:
            return [{**meta, "uuid": uuid} for uuid, meta in self.trashed.items()]

    def trashed_uuids(self) -> list[str]:
        with self._lock:
            return sorted(self.trashed.keys())

    # --- Maintenance ---------------------------------------------------------

    def forget(self, uuid: str) -> bool:
        """Remove a UUID's entry without trashing it. The next download run
        can fetch it again. Returns True if an entry was removed."""
        if not uuid:
            return False
        with self._lock:
            removed = self.entries.pop(uuid, None) is not None
        if removed:
            self._schedule_save()
        return removed

    def find_duplicate_filepaths(self, location: str | None = None) -> dict[str, list[str]]:
        """Return {filepath: [uuid, uuid, ...]} for every filepath shared by
        more than one entry. Caused by a TOCTOU race in older versions of the
        downloader: two threads picked the same target filename for distinct
        UUIDs, both manifest entries got created, but only one file actually
        landed on disk. If *location* is given, restrict to that location."""
        with self._lock:
            buckets: dict[str, list[str]] = {}
            for uuid, entry in self.entries.items():
                if location is not None and entry.get("location") != location:
                    continue
                fp = entry.get("filepath", "")
                if not fp:
                    continue
                key = os.path.normcase(os.path.normpath(fp))
                buckets.setdefault(key, []).append(uuid)
            return {fp: uuids for fp, uuids in buckets.items() if len(uuids) > 1}

    def forget_uuids(self, uuids) -> int:
        """Bulk-drop the given UUIDs from `entries`. Returns the count
        actually removed. Trashed set is untouched."""
        removed = 0
        with self._lock:
            for uuid in uuids:
                if self.entries.pop(uuid, None) is not None:
                    removed += 1
        if removed:
            self._schedule_save()
        return removed

    def upsert_from_disk(self, directory: str, location: str) -> dict:
        """Scan *directory* for SUNO_UUID-tagged audio files and reconcile the
        manifest with what's actually on disk.

        For each (filepath, uuid) pair found:
          - If uuid is unknown, add a new entry at *location*.
          - If uuid is known but its recorded filepath differs (file moved /
            renamed / dropped into a subfolder), update the filepath and
            promote location to *location* (handles users moving files from
            downloads/ into library/subfolder/ manually).

        Does NOT prune entries whose UUIDs are absent from disk — use
        Forget Missing for that. Returns counts: {added, updated, scanned}.
        """
        from core.utils import _scan_with_uuid_cache
        scanned = _scan_with_uuid_cache(directory, (".mp3", ".wav"))
        added = updated = 0
        with self._lock:
            for filepath, uuid in scanned.items():
                if not uuid:
                    continue
                existing = self.entries.get(uuid)
                if existing is None:
                    self.entries[uuid] = {
                        "title": os.path.splitext(os.path.basename(filepath))[0],
                        "artist": "",
                        "filepath": filepath,
                        "location": location,
                        "downloaded_at": _utcnow_iso(),
                    }
                    added += 1
                else:
                    changed = False
                    if existing.get("filepath") != filepath:
                        existing["filepath"] = filepath
                        changed = True
                    if existing.get("location") != location:
                        existing["location"] = location
                        changed = True
                    if changed:
                        updated += 1
        if added or updated:
            self._schedule_save()
        return {"added": added, "updated": updated, "scanned": len(scanned)}

    def prune_missing_at(self, location: str) -> list[str]:
        """Drop every entry at *location* whose `filepath` no longer exists on
        disk. Returns the list of UUIDs that were removed. Does NOT touch the
        trashed set (those are intentional permanent blocks)."""
        removed = []
        with self._lock:
            for uuid in list(self.entries.keys()):
                entry = self.entries[uuid]
                if entry.get("location") != location:
                    continue
                fp = entry.get("filepath", "")
                if fp and not os.path.exists(fp):
                    del self.entries[uuid]
                    removed.append(uuid)
        if removed:
            self._schedule_save()
        return removed

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, uuid: str) -> bool:
        return uuid in self.entries or uuid in self.trashed
