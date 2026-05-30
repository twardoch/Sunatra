"""Tests for version parsing used by the GitHub-release update check."""

from services.updater import _parse_version


def test_parse_basic():
    assert _parse_version("3.1.0") == (3, 1, 0)


def test_parse_strips_v_prefix():
    assert _parse_version("v3.1.0") == (3, 1, 0)
    assert _parse_version("V2.0") == (2, 0)


def test_parse_ignores_build_suffix():
    assert _parse_version("3.1.0+abc123") == (3, 1, 0)
    assert _parse_version("3.1.0-rc1") == (3, 1, 0)


def test_ordering():
    assert _parse_version("v3.2.0") > _parse_version("3.1.9")
    assert _parse_version("3.0.0") > _parse_version("0.0.0+unknown")
    assert _parse_version("3.1.0") == _parse_version("v3.1.0")


def test_garbage_is_safe():
    assert _parse_version("") == (0,)
    assert _parse_version("not-a-version") == (0,)
