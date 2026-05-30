"""Tests for the LibraryManifest dedupe/state source of truth."""

import json

from sunatra.core.manifest import LOCATION_DOWNLOADS, LOCATION_LIBRARY, LibraryManifest


def _mf(tmp_path):
    return LibraryManifest(path=str(tmp_path / "manifest.json"))


def test_add_get_remove(tmp_path):
    m = _mf(tmp_path)
    m.add("u1", title="T", artist="A", filepath="/x/t.mp3", location=LOCATION_DOWNLOADS)
    assert "u1" in m
    assert m.get("u1")["title"] == "T"
    m.remove("u1")
    assert m.get("u1") is None


def test_dedupe_set_includes_entries_and_trashed(tmp_path):
    m = _mf(tmp_path)
    m.add("u1")
    m.trash("u2", title="T2")
    assert m.dedupe_set() == {"u1", "u2"}


def test_trash_blocks_and_untrash_releases(tmp_path):
    m = _mf(tmp_path)
    m.add("u1", title="T")
    m.trash("u1")
    assert "u1" in m.dedupe_set()
    assert m.get("u1") is None  # entry removed when trashed
    m.untrash("u1")
    assert "u1" not in m.dedupe_set()


def test_move_updates_location(tmp_path):
    m = _mf(tmp_path)
    m.add("u1", filepath="/dl/t.mp3", location=LOCATION_DOWNLOADS)
    m.move("u1", "/lib/t.mp3", LOCATION_LIBRARY)
    assert m.get("u1")["location"] == LOCATION_LIBRARY
    assert m.get("u1")["filepath"] == "/lib/t.mp3"
    assert len(m.by_location(LOCATION_LIBRARY)) == 1
    assert len(m.by_location(LOCATION_DOWNLOADS)) == 0


def test_persistence_roundtrip(tmp_path):
    p = str(tmp_path / "m.json")
    m1 = LibraryManifest(path=p)
    m1.add("u1", title="Persist")
    m1.flush()
    m2 = LibraryManifest(path=p)
    assert m2.get("u1")["title"] == "Persist"


def test_legacy_trashed_list_migrates_to_dict(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"version": 1, "entries": {}, "trashed": ["old1", "old2"]}))
    m = LibraryManifest(path=str(p))
    assert set(m.trashed_uuids()) == {"old1", "old2"}


def test_corrupt_file_is_quarantined(tmp_path):
    p = tmp_path / "m.json"
    p.write_text("{ not valid json")
    m = LibraryManifest(path=str(p))
    assert len(m) == 0
    quarantined = list(tmp_path.glob("m.json.corrupt-*"))
    assert quarantined, "corrupt manifest should be quarantined"


def test_prune_missing_at(tmp_path):
    m = _mf(tmp_path)
    present = tmp_path / "here.mp3"
    present.write_bytes(b"x")
    m.add("u1", filepath=str(present), location=LOCATION_LIBRARY)
    m.add("u2", filepath=str(tmp_path / "gone.mp3"), location=LOCATION_LIBRARY)
    removed = m.prune_missing_at(LOCATION_LIBRARY)
    assert removed == ["u2"]
    assert "u1" in m and "u2" not in m
