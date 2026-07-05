---
title: FAQ
layout: default
nav_order: 7
---

# FAQ

## My antivirus flagged Sunatra. Is it malware?

No. Sunatra is a PyInstaller-bundled Python app, and unsigned single-file bundles from
small projects are a classic false-positive for heuristic scanners — they see a program
that unpacks itself and reaches the network, which is exactly what a downloader does. The
source is open; you can read every line or [build it yourself](building.md) if you would
rather not trust a binary.

## macOS says the app is damaged or from an unidentified developer.

The macOS build is unsigned and un-notarized, so Gatekeeper blocks a plain double-click.
Right-click the app and choose **Open** the first time; macOS then remembers your choice.
Code signing and notarization are on the roadmap but require an Apple Developer account.

## Nothing plays. Downloads work, but no sound.

Sunatra plays through [VLC](https://www.videolan.org/), which is **not** bundled. Install
VLC system-wide and restart Sunatra. Downloading and library management never needed VLC —
only playback does.

## A feature stopped working after a Suno update.

Sunatra talks to Suno's private, undocumented API. When Suno changes an endpoint or a
response shape, features that depend on it can break until Sunatra catches up. That is the
cost of an unofficial tool. Please [open an issue](https://github.com/twardoch/Sunatra/issues)
with what you saw.

## Where does Sunatra store my data?

In your OS's standard app-data directory (via `appdirs`, under `Sunatra/twardoch`):
config, the library manifest, the UUID cache, and your saved prompts. Your music lives in
the **Downloads** and **Library** folders you choose. Nothing is uploaded anywhere except
Suno itself and, only if you opt in, crash reports.

## Is my Suno token safe?

The token stays on your machine — in Sunatra's config file — and is sent only to Suno as a
bearer token on API calls. The browser extension hands it to the app over a localhost-only
listener. Sunatra never transmits it to any third party.

## Will there be a signed / store-distributed build?

That is the plan: a signed Firefox add-on and code-signed desktop binaries. Until then,
the "unsigned indie build" steps above are the intended path.
