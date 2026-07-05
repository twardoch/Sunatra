---
title: Library filters
layout: default
nav_order: 5
---

# Library filters

When Sunatra walks your Suno feed, each track is tested against the filters you set in
the Downloader tab. A track is downloaded only if it passes every active filter. The
rules live in one pure, unit-tested function — `song_passes_filters()` in
`sunatra/core/downloader.py` — so what the UI promises is exactly what the code does.

## What each filter keeps

| Filter | Effect |
|--------|--------|
| *(none)* | Everything with a downloadable audio URL. Trashed tracks are still excluded unless you ask for them. |
| **Liked** | Only tracks you liked. Suno has shipped that signal three ways over time — a boolean, a reaction (`L`), and an up-vote — and any one counts. |
| **Disliked** | Only tracks marked disliked (reaction `D` or a down-vote). |
| **Hide disliked** | Drops disliked tracks (unless **Disliked** is explicitly on). |
| **Trash** | *Includes* trashed tracks, which are otherwise always skipped. |
| **Public** | Only tracks that are public. |
| **Private** | Only tracks that are not public. |
| **Uploads** | Only clips you uploaded (as opposed to generated). |
| **Covers** | Only cover clips. |
| **Personas** | Only tracks made with a persona. |
| **Full songs** | Drops short clips — keeps tracks longer than ~60s or explicit concatenations. |
| **Hide studio clips** | Drops `studio_clip` items. |
| **Hide stems** | Drops stem tracks (overridden when **Stems only** is active). |
| **Stems only** | Keeps *only* stem tracks. |
| **Search** | Free-text match across a track's title, tags, and prompt. |

## Two rules that always apply

- **Audio required.** A track with no downloadable audio URL is skipped — except during a
  scan-only pass, which classifies the feed without downloading.
- **Trash is opt-in.** Trashed tracks never download unless the **Trash** filter is on.
  They also stay in a permanent block list (see below), so you can throw something away
  and trust it will not creep back on the next sync.

## Why re-runs are fast

Every downloaded track carries its Suno **UUID** as an ID3 tag. Sunatra keeps a manifest
of every UUID it has seen, plus a separate set of trashed UUIDs. The downloader skips
anything already in that combined set, so a second run only fetches genuinely new music —
no re-walking your whole library, no re-parsing every file.
