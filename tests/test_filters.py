"""Tests for the pure feed-filter predicate (upstream issue #3: Liked filter)."""

from sunatra.core.downloader import song_passes_filters


def _song(**over):
    base = {
        "id": "uuid-1",
        "title": "Song",
        "audio_url": "https://x/audio.mp3",
        "metadata": {"type": "gen"},
    }
    base.update(over)
    return base


def test_no_id_rejected():
    assert song_passes_filters({"audio_url": "x"}, {}) is False


def test_no_audio_rejected_unless_scan():
    s = _song(audio_url=None)
    assert song_passes_filters(s, {}) is False
    assert song_passes_filters(s, {}, scan_only=True) is True


def test_liked_filter_keeps_only_liked_via_boolean():
    liked = _song(is_liked=True)
    plain = _song(is_liked=False)
    assert song_passes_filters(liked, {"liked": True}) is True
    assert song_passes_filters(plain, {"liked": True}) is False


def test_liked_filter_recognises_reaction_and_vote():
    via_reaction = _song(reaction={"reaction_type": "L"})
    via_vote = _song(vote="up")
    assert song_passes_filters(via_reaction, {"liked": True}) is True
    assert song_passes_filters(via_vote, {"liked": True}) is True


def test_no_filter_keeps_everything():
    assert song_passes_filters(_song(is_liked=False), {}) is True


def test_disliked_filter():
    disliked = _song(reaction={"reaction_type": "D"})
    assert song_passes_filters(disliked, {"disliked": True}) is True
    assert song_passes_filters(_song(), {"disliked": True}) is False


def test_hide_disliked():
    disliked = _song(vote="down")
    assert song_passes_filters(disliked, {"hide_disliked": True}) is False
    assert song_passes_filters(_song(), {"hide_disliked": True}) is True


def test_trash_excluded_by_default_but_included_when_requested():
    trashed = _song(is_trashed=True)
    assert song_passes_filters(trashed, {}) is False
    assert song_passes_filters(trashed, {"trashed": True}) is True


def test_public_and_private():
    pub = _song(is_public=True)
    priv = _song(is_public=False)
    assert song_passes_filters(pub, {"is_public": True}) is True
    assert song_passes_filters(priv, {"is_public": True}) is False
    assert song_passes_filters(priv, {"is_private": True}) is True
    assert song_passes_filters(pub, {"is_private": True}) is False


def test_type_uploads():
    upload = _song(metadata={"type": "upload"})
    gen = _song(metadata={"type": "gen"})
    assert song_passes_filters(upload, {"type": "uploads"}) is True
    assert song_passes_filters(gen, {"type": "uploads"}) is False


def test_full_song_heuristic():
    short = _song(metadata={"type": "gen", "duration": 30})
    long = _song(metadata={"type": "gen", "duration": 120})
    concat = _song(metadata={"type": "concat", "duration": 10})
    assert song_passes_filters(short, {"full_song": True}) is False
    assert song_passes_filters(long, {"full_song": True}) is True
    assert song_passes_filters(concat, {"full_song": True}) is True


def test_cover_and_persona():
    cover = _song(metadata={"type": "cover"})
    persona = _song(metadata={"type": "gen", "persona_id": "p1"})
    assert song_passes_filters(cover, {"is_cover": True}) is True
    assert song_passes_filters(_song(), {"is_cover": True}) is False
    assert song_passes_filters(persona, {"is_persona": True}) is True
    assert song_passes_filters(_song(), {"is_persona": True}) is False


def test_search_text_matches_title_tags_prompt():
    s = _song(title="Midnight Drive", metadata={"type": "gen", "tags": "synthwave", "prompt": "neon city"})
    assert song_passes_filters(s, {"search_text": "synthwave"}) is True
    assert song_passes_filters(s, {"search_text": "NEON"}) is True
    assert song_passes_filters(s, {"search_text": "jazz"}) is False


def test_stems_only_requires_stem():
    assert song_passes_filters(_song(), {}, stems_only=True, is_stem=False) is False
    assert song_passes_filters(_song(), {}, stems_only=True, is_stem=True) is True


def test_hide_stems_unless_stems_only():
    assert song_passes_filters(_song(), {"hide_gen_stems": True}, is_stem=True) is False
    # Stems Only overrides Hide Stems.
    assert song_passes_filters(_song(), {"hide_gen_stems": True}, stems_only=True, is_stem=True) is True
