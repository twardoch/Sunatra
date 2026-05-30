"""Tests for centralized data-dir resolution and legacy migration."""

import os

from core import app_meta


def _redirect_appdirs(monkeypatch, root):
    """Map every (name, author) pair to a distinct subdir under *root* so we can
    simulate the legacy SunoSync dirs and the new Sunatra dir on disk."""
    def fake(name, author):
        return os.path.join(root, f"{name}__{author}")
    monkeypatch.setattr(app_meta.appdirs, "user_data_dir", fake)


def test_user_data_dir_is_created(tmp_path, monkeypatch):
    _redirect_appdirs(monkeypatch, str(tmp_path))
    d = app_meta.user_data_dir()
    assert os.path.isdir(d)
    assert d.endswith(os.path.join("Sunatra__twardoch"))


def test_migration_copies_both_legacy_dirs(tmp_path, monkeypatch):
    _redirect_appdirs(monkeypatch, str(tmp_path))

    legacy_config = os.path.join(str(tmp_path), "SunoSync__InternetThot")
    legacy_vault = os.path.join(str(tmp_path), "SunoSync__SunoSync")
    os.makedirs(legacy_config)
    os.makedirs(legacy_vault)
    with open(os.path.join(legacy_config, "config.json"), "w") as f:
        f.write('{"token": "abc"}')
    with open(os.path.join(legacy_vault, "prompts.json"), "w") as f:
        f.write('{"p": 1}')

    copied = app_meta.migrate_legacy_data()
    assert copied == 2

    new_dir = app_meta.user_data_dir()
    assert os.path.exists(os.path.join(new_dir, "config.json"))
    assert os.path.exists(os.path.join(new_dir, "prompts.json"))


def test_migration_is_idempotent_and_nondestructive(tmp_path, monkeypatch):
    _redirect_appdirs(monkeypatch, str(tmp_path))
    legacy = os.path.join(str(tmp_path), "SunoSync__InternetThot")
    os.makedirs(legacy)
    with open(os.path.join(legacy, "config.json"), "w") as f:
        f.write("{}")

    assert app_meta.migrate_legacy_data() == 1
    # Second run copies nothing and leaves the legacy copy intact.
    assert app_meta.migrate_legacy_data() == 0
    assert os.path.exists(os.path.join(legacy, "config.json"))


def test_migration_does_not_overwrite_existing(tmp_path, monkeypatch):
    _redirect_appdirs(monkeypatch, str(tmp_path))
    new_dir = app_meta.user_data_dir()
    with open(os.path.join(new_dir, "config.json"), "w") as f:
        f.write('{"keep": true}')

    legacy = os.path.join(str(tmp_path), "SunoSync__InternetThot")
    os.makedirs(legacy)
    with open(os.path.join(legacy, "config.json"), "w") as f:
        f.write('{"old": true}')

    assert app_meta.migrate_legacy_data() == 0
    with open(os.path.join(new_dir, "config.json")) as f:
        assert "keep" in f.read()
