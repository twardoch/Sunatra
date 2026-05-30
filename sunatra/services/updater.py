import re
import threading

import requests

from sunatra.core.app_meta import GITHUB_RELEASES_API, GITHUB_RELEASES_URL
from sunatra.core.version import __version__ as CURRENT_VERSION


def _parse_version(text: str) -> tuple[int, ...]:
    """Parse a version string like ``v3.1.0`` / ``3.1.0`` / ``3.1.0+abc`` into a
    comparable tuple of ints. Non-numeric/build suffixes are ignored."""
    core = re.split(r"[+\-]", text.strip().lstrip("vV"), maxsplit=1)[0]
    parts = []
    for piece in core.split("."):
        m = re.match(r"\d+", piece)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts) or (0,)


class Updater:
    @staticmethod
    def check_for_updates(callback):
        """Check the latest GitHub Release in a background thread.

        callback: function(latest_version, download_url) -> None, invoked only
        when a strictly newer release exists.
        """
        def _check():
            try:
                resp = requests.get(
                    GITHUB_RELEASES_API,
                    timeout=5,
                    headers={"Accept": "application/vnd.github+json"},
                )
                if resp.status_code != 200:
                    return
                data = resp.json()
                tag = data.get("tag_name") or data.get("name")
                if not tag:
                    return
                download_url = data.get("html_url") or GITHUB_RELEASES_URL
                if _parse_version(tag) > _parse_version(CURRENT_VERSION):
                    callback(tag.lstrip("vV"), download_url)
            except Exception as e:
                print(f"[Updater] Check failed: {e}")

        threading.Thread(target=_check, daemon=True).start()
