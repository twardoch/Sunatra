"""Tests for crash-report PII scrubbing."""

from services.telemetry import REDACTED, scrub_event


def test_redacts_token_and_cookie_keys():
    event = {
        "request": {
            "headers": {"Authorization": "Bearer secret", "Cookie": "__client=abc"},
            "data": {"token": "xyz", "title": "Song"},
        },
        "extra": {"api_key": "k", "note": "ok"},
    }
    out = scrub_event(event)
    assert out["request"]["headers"]["Authorization"] == REDACTED
    assert out["request"]["headers"]["Cookie"] == REDACTED
    assert out["request"]["data"]["token"] == REDACTED
    assert out["extra"]["api_key"] == REDACTED
    # Non-sensitive values are preserved.
    assert out["request"]["data"]["title"] == "Song"
    assert out["extra"]["note"] == "ok"


def test_handles_lists_and_nesting():
    event = {"breadcrumbs": [{"data": {"secret": "s", "ok": 1}}]}
    out = scrub_event(event)
    assert out["breadcrumbs"][0]["data"]["secret"] == REDACTED
    assert out["breadcrumbs"][0]["data"]["ok"] == 1


def test_case_insensitive_keys():
    out = scrub_event({"ACCESS_TOKEN": "x", "Secret_Value": "y"})
    assert out["ACCESS_TOKEN"] == REDACTED
    assert out["Secret_Value"] == REDACTED


def test_never_raises_on_garbage():
    assert scrub_event(None) is None or scrub_event(None) == {}
    # A weird event still returns something (or None), never raises.
    scrub_event({"x": object()})
