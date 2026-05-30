"""Single source of the running application version.

Resolution order:
  1. ``core/_version.py`` — written at build time by hatch-vcs from the latest
     semver git tag (git-ignored; present in release builds).
  2. Installed package metadata (when installed via ``pip install .``).
  3. A safe fallback for source checkouts without tags or a build step.
"""

try:
    from sunatra.core._version import __version__  # type: ignore
except Exception:
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        try:
            __version__ = _pkg_version("sunatra")
        except PackageNotFoundError:
            __version__ = "0.0.0+unknown"
    except Exception:
        __version__ = "0.0.0+unknown"
