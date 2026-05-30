"""Tests for filename safety and UUID metadata round-tripping."""

import os
import unicodedata
import wave
from concurrent.futures import ThreadPoolExecutor

from sunatra.core import utils

# --- sanitize_filename -------------------------------------------------------

def test_sanitize_strips_forbidden_chars():
    out = utils.sanitize_filename('a<b>c:d"e/f\\g|h?i*j')
    for bad in '<>:"/\\|?*':
        assert bad not in out


def test_sanitize_nfc_normalisation():
    # "é" as combining sequence (NFD) vs precomposed (NFC) must collapse to one.
    nfd = unicodedata.normalize("NFD", "café")
    nfc = unicodedata.normalize("NFC", "café")
    assert nfd != nfc  # different byte sequences going in
    assert utils.sanitize_filename(nfd) == utils.sanitize_filename(nfc)


def test_sanitize_empty_and_dots():
    assert utils.sanitize_filename("") == "untitled"
    assert utils.sanitize_filename("   ...  ") == "untitled"


def test_sanitize_windows_reserved():
    assert utils.sanitize_filename("CON") == "_CON"
    assert utils.sanitize_filename("nul.mp3") == "_nul.mp3"


def test_sanitize_truncates():
    out = utils.sanitize_filename("x" * 500, maxlen=200)
    assert len(out) <= 200


# --- reserve_unique_path (issue #6: race-safe naming) ------------------------

def test_reserve_unique_path_serial(tmp_path):
    target = str(tmp_path / "song.mp3")
    first = utils.reserve_unique_path(target)
    second = utils.reserve_unique_path(target)
    assert first != second
    assert os.path.exists(first) and os.path.exists(second)


def test_reserve_unique_path_concurrent(tmp_path):
    """Many threads racing for the same name must each get a distinct file —
    no overwrites (the upstream #6 race)."""
    target = str(tmp_path / "race.mp3")
    with ThreadPoolExecutor(max_workers=8) as ex:
        paths = list(ex.map(lambda _: utils.reserve_unique_path(target), range(40)))
    assert len(set(paths)) == len(paths) == 40


# --- UUID metadata round-trip ------------------------------------------------

def _make_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)


def test_uuid_embed_and_extract(tmp_path):
    wav = tmp_path / "track.wav"
    _make_wav(wav)
    utils.embed_metadata(
        str(wav),
        image_url=None,
        title="Test",
        uuid="abc-123-uuid",
        created_at="2026-01-02 03:04:05",
    )
    assert utils.get_uuid_from_file(str(wav)) == "abc-123-uuid"


def test_uuid_extract_missing_returns_none(tmp_path):
    wav = tmp_path / "bare.wav"
    _make_wav(wav)
    assert utils.get_uuid_from_file(str(wav)) is None
