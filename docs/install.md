---
title: Install
layout: default
nav_order: 2
---

# Install

Sunatra ships as a pre-built executable for **Windows, macOS, and Linux**. Download the
one for your OS from the [Releases page](https://github.com/twardoch/Sunatra/releases/latest).

| OS | Download | First run |
|----|----------|-----------|
| Windows | `Sunatra-windows.zip` → `Sunatra.exe` | Double-click. Some antivirus may flag an unsigned indie build — see the [FAQ](faq.md). |
| macOS | `Sunatra-macos.zip` → `Sunatra.app` | Right-click → **Open** the first time (the build is unsigned). |
| Linux | `Sunatra-linux.zip` → `Sunatra` | `chmod +x Sunatra` then run it. |

## You also need VLC

Sunatra plays audio through [VLC](https://www.videolan.org/). VLC is **not** bundled —
install it system-wide once and Sunatra finds it. Without VLC, downloading and library
management still work; playback does not.

## Prefer to run from source?

If you have [uv](https://docs.astral.sh/uv/) and git, you can skip the binary entirely:

```bash
git clone https://github.com/twardoch/Sunatra.git
cd Sunatra
uv run python -m sunatra      # syncs deps and launches the app
```

See [Build from source](building.md) for packaging your own executable or installing the
`sunatra` command.
