---
layout: home
title: Home
nav_order: 1
---

# Sunatra

**Your World, Your Music. Seamlessly Synced.**

Sunatra is a cross-platform desktop app for your [Suno](https://suno.com) AI music
library. It bulk-downloads every track you own, writes real metadata into the files,
gives you a dark-themed library to play them back, keeps a vault of your best prompts,
and ships companion browser extensions so you never copy a cookie by hand.

![Sunatra](assets/icon.png){: style="max-width:320px"}

> Sunatra is the actively maintained successor to *SunoSync*. It is unofficial and not
> affiliated with Suno AI.

## What it does

- **Downloads your whole library.** Filter by Liked, Public, Trash, Uploads, Covers,
  Personas and more; pick **MP3** or lossless **WAV**. A manifest remembers every UUID,
  so a second run only fetches what is new.
- **Embeds metadata that survives.** Title, artist, lyrics, cover art, the Suno `UUID`,
  and the original Suno creation date are written into the audio tags — not a sidecar
  file that gets lost.
- **Plays your tracks.** A dark library browser with clean titles, Like/Star/Trash
  tagging, and a stats dashboard, powered by VLC.
- **Keeps your prompts.** A vault to save and one-click-copy the prompts that worked.
- **Handles auth for you.** Chrome and Firefox extensions sync your Suno session token
  to the app automatically.

## Start here

1. [Install](install.md) — grab the binary for your OS.
2. [Connect your Suno account](authentication.md) — extension or manual cookie.
3. [Browser extension](extension.md) — the one-click token path.
4. [Library filters](filters.md) — what each download filter actually keeps.
5. [Build from source](building.md) — run and package it yourself.
6. [FAQ](faq.md) — antivirus flags, unsigned binaries, VLC.

## A note on how it talks to Suno

Sunatra speaks to Suno's private `studio-api.prod.suno.com` API with your own session
cookie. That API is undocumented and can change without warning; when a Suno update
breaks a feature, that is usually why. Nothing is sent anywhere except Suno and, if you
opt in, crash reports.
