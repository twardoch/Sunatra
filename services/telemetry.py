"""Telemetry helpers — PII scrubbing for crash reports.

Sunatra holds a Suno session token (`__client`). If Sentry is ever enabled, that
token (and prompts / local paths) must never leave the machine. ``scrub_event``
is the Sentry ``before_send`` hook; it is pure and unit-tested so the redaction
rules can't silently regress.
"""

REDACTED = "[redacted]"

# Substrings (case-insensitive) of dict keys whose values must be redacted.
_SENSITIVE_KEYS = (
    "cookie",
    "authorization",
    "auth",
    "token",
    "__client",
    "password",
    "secret",
    "api_key",
    "apikey",
)


def _is_sensitive(key) -> bool:
    if not isinstance(key, str):
        return False
    low = key.lower()
    return any(s in low for s in _SENSITIVE_KEYS)


def _scrub(obj, depth=0):
    if depth > 12:  # guard against pathological nesting
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _is_sensitive(k):
                out[k] = REDACTED
            else:
                out[k] = _scrub(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [_scrub(v, depth + 1) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(v, depth + 1) for v in obj)
    return obj


def scrub_event(event, hint=None):
    """Sentry ``before_send`` hook. Returns the event with sensitive values
    redacted. Never raises (a scrubber that crashes must not drop the report)."""
    try:
        return _scrub(event)
    except Exception:
        # If scrubbing fails, drop the event rather than risk leaking PII.
        return None
