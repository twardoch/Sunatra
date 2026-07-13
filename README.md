# SunoSync

**Your World, Your Music. Seamlessly Synced.**

SunoSync is a desktop ecosystem for your Suno AI music generation. It combines a powerful bulk downloader, a rich music library, a prompt vault, live radio broadcasting, and a mobile bridge into one seamless application.

![SunoSync Splash](resources/splash.png)

---

> **🙏 This is a fork — credit where it's due**
>
> SunoSync was **created by [@InternetThot](https://github.com/sunsetsacoustic)** (sunsetsacoustic on GitHub). The original project lives at **[github.com/sunsetsacoustic/SunoSync](https://github.com/sunsetsacoustic/SunoSync)** — all the hard early work is theirs.
>
> This repository ([**Caeldeth/SunoSync**](https://github.com/Caeldeth/SunoSync)) is a community fork that builds on top of it. It is **not** a reskin-and-rename: see [**What's different in this fork**](#-whats-different-in-this-fork) for the actual changes.
>
> **If SunoSync is useful to you, please support the original creator** — every donate link below goes to **them**, not to this fork.

---

## ❤️ Support the original creator

All donations go to **@InternetThot**, the author of SunoSync:

- **Ko-fi:** <https://ko-fi.com/s/374c24251c>  *(PayPal accepted — $3 or pay what you want)*
- **Gumroad:** <https://justinmurray99.gumroad.com/l/rrxty>  *($3 or pay what you want)*
- **Buy Me a Coffee:** <https://buymeacoffee.com/audioalchemy>

**Community & support (original project):** [Discord](https://discord.gg/kZSc8sKUZR)

> The Ko-fi / Gumroad links above are the original author's official builds. **This fork does not sell builds** — to run this fork, [build it from source](#-building-from-source).

## ✨ What's different in this fork

This fork is strictly ahead of upstream, adding real functionality rather than a coat of paint:

- **Firefox companion extension** — auto token-sync for Firefox, alongside the existing Chrome extension (upstream shipped Chrome only).
- **Library / Downloads split + Ignored tab** — downloads land in a staging area and are promoted to the Library, with a dedicated view for ignored/trashed tracks.
- **Manifest-based dedup & UUID cache** — a persistent library manifest and on-disk UUID cache make rescans fast and fix "ghost song" re-downloads; config writes are debounced.
- **libvlc log silencing & build fixes** — the audio engine's plugin-loader chatter is suppressed and packaging is fixed.
- **Discord Rich Presence disabled by default** — upstream bundled a Discord application ID that isn't ours to use; it's stubbed out until a SunoSync-owned app ID is in place.
- **House "Dubhaimid" dark theme** — a restyle to a neutral charcoal + steel-blue palette (Segoe UI, flat surfaces).
- **Code-review & hardening pass** — fixes for a crash when opening the download folder, a crash when opening the Downloader tab, a UI freeze on track change, safer library-scan path handling, a socket leak, and removal of dead code.

## 🌟 Key Features

### 🎨 Modern UI
- **Dark Theme**: A responsive interface built with CustomTkinter.
- **Compact Sidebar**: Optimized navigation with a sticky "Settings" footer for easy access on any screen size.
- **Inline Controls**: Quick access to Workspaces and Playlists via inline dropdown menus.

### 📥 Smart Downloader
- **Advanced Filtering**: Filter by Status (Liked, Public, Trash) and Type (Generations, Uploads) with a robust Filter Bar.
- **Bulk Downloading**: Download your entire Suno library in one click.
- **Smart Sync**: Only downloads new songs, skipping existing files.
- **Format Choice**: **MP3** (Compact) or **WAV** (Lossless).
- **Metadata Embedding**: Automatically embeds Title, Artist, **Lyrics**, and Cover Art into audio tags.

### 📚 Music Library
- **Visual Browser**: Browse your collection with a clean, dark-themed grid.
- **Clean Titles**: Automatically sanitizes messy raw titles into readable text.
- **Tag System**: Organize with Like 👍, Star ⭐, and Trash 🗑️.
- **Stats Dashboard**: View detailed analytics of your library (Top Genres, Monthly Activity, etc.).

### 🔌 Browser Extension Integration
- **Auto-Token Sync**: Never manually copy cookies again. Companion extensions for Chrome and Firefox automatically sync your Suno session with the desktop app.

### 📻 Suno On-Air & Mobile Bridge
- **Live Radio**: Broadcast your library as a live web radio station to share with friends.
- **Mobile Bridge**: Scan a QR code to stream your library directly to your phone browser.

### 🔐 Prompt Vault
- **Save Your Prompts**: Never lose a great prompt again. Save and organize your best prompts.
- **One-Click Copy**: Quickly copy prompts to clipboard for reuse in Suno.

## 🚀 Getting Started

This fork is distributed as source (see [Building from Source](#-building-from-source)).

1.  **Install VLC**: Ensure [VLC Media Player](https://www.videolan.org/) is installed (required for the audio engine).
2.  **Run**: Launch with `python main.py` (or build the EXE).
3.  **Connect**:
    - **Option A (Easy)**: Install the SunoSync browser extension (Chrome or Firefox — see below). It will automatically detect the app and sync your token.
    - **Option B (Manual)**: Click "Get Token", log in to Suno.com, open DevTools → Application → Cookies, and copy the `__client` cookie.

## 🔌 Browser Extension (Auto-Auth)

SunoSync ships with companion extensions for Chrome and Firefox that make authentication automatic.

### Chrome / Edge / other Chromium

1.  **Open Extensions**: Go to `chrome://extensions/`.
2.  **Enable Developer Mode**: Toggle the switch in the top right.
3.  **Load Unpacked**: Click the button and select the `chrome_extension` folder inside the SunoSync directory.
4.  **Done!**: The extension will now automatically detect when SunoSync is open and sync your session token.

### Firefox (121+)

1.  **Open Add-ons Debugging**: Go to `about:debugging#/runtime/this-firefox`.
2.  **Load Temporary Add-on**: Click the button and select `firefox_extension/manifest.json`.
3.  **Done!** — Note: temporary add-ons are removed when Firefox closes; for a persistent install you'll need a Mozilla-signed build (planned).

## 🛠️ Building from Source

### Prerequisites
- **Python 3.10+**
- **Git**
- **VLC Media Player**

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Caeldeth/SunoSync.git
    cd SunoSync
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```

### Compiling
To build the standalone `.exe` file:

```bash
pyinstaller SunoSync.spec
```
The executable will be in the `dist/` folder.

## 🔄 Updating

1.  `git pull` to get the latest code.
2.  `pip install -r requirements.txt` to pick up any new dependencies.
3.  Run `python main.py` or rebuild the EXE.

Your settings and library data are preserved across updates.

## 🔒 Transparency

SunoSync is an indie tool built with Python.
- **Crash Shield**: Optional error reporting (Sentry) helps diagnose bugs faster. It is disabled unless a DSN is configured.
- **False Positives**: Some antivirus software may flag the app because it is not digitally signed by a corporation. This is normal for open-source Python tools.

## 📜 Credits & License

- **Original author:** [@InternetThot](https://github.com/sunsetsacoustic) — created SunoSync ([upstream repo](https://github.com/sunsetsacoustic/SunoSync)). Please [support their work](#-support-the-original-creator).
- **This fork:** maintained by [Caeldeth](https://github.com/Caeldeth).
- **License:** MIT (see [LICENSE](LICENSE)).

---
*SunoSync is an unofficial tool and is not affiliated with Suno AI.*
