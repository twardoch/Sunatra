---
title: Connect your account
layout: default
nav_order: 3
---

# Connect your Suno account

Sunatra needs your Suno session token to fetch your library. The token is the value of
the `__client` cookie that suno.com sets when you log in. There are two ways to get it
into Sunatra.

## Easy: the browser extension

Install the Sunatra extension for Chrome or Firefox (see [Browser extension](extension.md)).
When Sunatra is running, the extension detects it, reads the `__client` cookie, and posts
it straight to the app. You click nothing in a cookie inspector, and the token refreshes
itself as you keep browsing Suno.

This is the recommended path. It is also the least error-prone: session tokens expire,
and the extension re-syncs the fresh one automatically.

## Manual: copy the cookie

If you would rather not install an extension:

1. In Sunatra, click **Get Token** — it opens suno.com.
2. Log in to Suno.
3. Open your browser's DevTools → **Application** → **Cookies** → `https://suno.com`.
4. Copy the value of the `__client` cookie.
5. Paste it into Sunatra's token field.

The manual token is a snapshot. When it expires, Suno starts returning empty feeds or
authorization errors and you repeat these steps. The extension exists precisely to spare
you that loop.

## How the token flows

The extension POSTs the cookie to a local listener the app runs on
`127.0.0.1:38945` (`TokenServer`). Nothing leaves your machine except the normal
requests to Suno. Sunatra stores the token in its own config file and sends it as
`Authorization: Bearer <token>` on every Suno API call.

## When a token stops working

- **Empty library or "unauthorized":** the token expired. Re-sync with the extension, or
  copy a fresh `__client` cookie.
- **Some tracks missing:** that is usually a [filter](filters.md), not auth — check what
  the active download filters keep.
