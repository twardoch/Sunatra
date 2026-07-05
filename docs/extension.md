---
title: Browser extension
layout: default
nav_order: 4
---

# Browser extension

The companion extension does one job: read your Suno `__client` cookie and hand it to
the running Sunatra app, so you never touch a cookie inspector. Chrome and Firefox
builds live in the repository as `chrome_extension/` and `firefox_extension/` — two
near-identical MV3 extensions.

## Chrome / Edge / Chromium

1. Open `chrome://extensions/`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and select the `chrome_extension/` folder.

The extension stays installed across restarts.

## Firefox (121+)

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on**.
3. Select `firefox_extension/manifest.json`.

Temporary add-ons are removed when Firefox closes, so you reload it each session. A
signed build that installs permanently is planned.

## How it works

While Sunatra is running it listens on `127.0.0.1:38945`. The extension's content script
reads the `__client` cookie on suno.com and POSTs it to that local listener; Sunatra
writes it into config and updates the Downloader tab. The token refreshes as you keep
browsing, so an expired session heals itself.

Nothing is transmitted off your machine — the only network destinations are suno.com
(to browse) and localhost (to hand the token to the app).

## If it does not connect

- **Sunatra must be running first.** The extension posts to a local port; if the app is
  closed there is nothing listening.
- **You must be logged in to suno.com** in that browser — no cookie, no token.
- If you changed the app's token-server port in a custom build, the extension's
  `background.js` must point at the same port.
