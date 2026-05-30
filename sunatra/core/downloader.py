import os
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from sunatra.core.utils import (
    RateLimiter,
    embed_metadata,
    get_downloaded_uuids,
    reserve_unique_path,
    sanitize_filename,
)

GEN_API_BASE = "https://studio-api.prod.suno.com"


def song_passes_filters(song_data, filters, *, stems_only=False, scan_only=False, is_stem=False):
    """Pure predicate: does *song_data* survive the UI *filters*?

    Extracted from ``SunoDownloader.run`` so the filtering rules (notably the
    "Liked" filter — upstream issue #3) are independently unit-testable and not
    buried in a 1000-line network loop. No I/O; dedupe is handled by the caller.

    Liked detection is intentionally robust: Suno has shipped the signal as a
    boolean (``is_liked``), a reaction (``reaction.reaction_type == 'L'``), and a
    vote (``vote == 'up'``) across API revisions — any one counts as liked.
    """
    filters = filters or {}

    if not song_data or not song_data.get("id"):
        return False

    metadata = song_data.get("metadata") or {}
    clip_type = metadata.get("type", "")

    reaction = song_data.get("reaction") or {}
    reaction_type = reaction.get("reaction_type", "")
    vote = song_data.get("vote", "") or metadata.get("vote", "")
    is_liked = bool(song_data.get("is_liked", False)) or reaction_type == "L" or vote == "up"
    is_disliked = reaction_type == "D" or vote == "down"

    is_trashed = song_data.get("is_trashed", False)
    is_public = song_data.get("is_public", False)
    audio_url = song_data.get("audio_url")

    # 0. Need audio unless we're only scanning (classification) the feed.
    if not audio_url and not scan_only:
        return False
    # 1. Trash
    if not filters.get("trashed", False) and is_trashed:
        return False
    # 2. Stems (Hide Stems is overridden when Stems Only is active)
    if filters.get("hide_gen_stems", False) and not stems_only and is_stem:
        return False
    if stems_only and not is_stem:
        return False
    # 3. Liked / Disliked
    if filters.get("liked", False) and not is_liked:
        return False
    if filters.get("disliked", False) and not is_disliked:
        return False
    if filters.get("hide_disliked", False) and not filters.get("disliked", False) and is_disliked:
        return False
    # 5. Public / Private
    if filters.get("is_public", False) and not is_public:
        return False
    if filters.get("is_private", False) and is_public:
        return False
    # 6. Studio / 7. Type
    if filters.get("hide_studio_clips", False) and clip_type == "studio_clip":
        return False
    if filters.get("type", "all") == "uploads" and clip_type != "upload":
        return False
    # 8. Full song (heuristic: long or concatenated)
    if filters.get("full_song", False):
        duration = metadata.get("duration", 0) or 0
        if duration < 60 and clip_type != "concat":
            return False
    # 9. Cover / 10. Persona
    if filters.get("is_cover", False) and clip_type != "cover":
        return False
    if filters.get("is_persona", False) and not metadata.get("persona_id"):
        return False
    # 11. Free-text search across title/tags/prompt
    search_text = (filters.get("search_text", "") or "").strip().lower()
    if search_text:
        title = (song_data.get("title", "") or "").lower()
        tags = (metadata.get("tags", "") or "").lower()
        prompt = (metadata.get("prompt", "") or "").lower()
        if search_text not in f"{title} {tags} {prompt}":
            return False

    return True


class Signal:
    """A simple signal implementation for observer pattern."""
    def __init__(self, arg_types=None):
        self._subscribers = []
        self.arg_types = arg_types

    def connect(self, callback):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def emit(self, *args):
        for callback in self._subscribers:
            try:
                callback(*args)
            except Exception:
                traceback.print_exc()


class DownloaderSignals:
    """Container for all signals emitted by SunoDownloader."""
    def __init__(self):
        self.status_changed = Signal(str)       # msg
        self.log_message = Signal((str, str))   # msg, type (info, error, success, downloading)
        self.progress_updated = Signal(int)     # percentage (optional usage)
        self.download_complete = Signal(bool)   # success
        self.error_occurred = Signal(str)       # error message
        self.thumbnail_fetched = Signal((bytes, str)) # data, title/id context

        # New Signals for Queue
        self.song_started = Signal((str, str, bytes, dict)) # uuid, title, thumbnail_data, metadata
        self.song_updated = Signal((str, str, int))   # uuid, status, progress
        self.song_finished = Signal((str, bool, str)) # uuid, success, filepath
        self.song_found = Signal((dict,))             # metadata (for preload)
        # Preload summary: emitted once at end of a scan_only run with bucket
        # counts/lists so the UI can offer "Re-download Missing" actions.
        # Shape: {"new": [meta...], "on_disk": [meta...], "missing_on_disk": [meta...], "trashed": [meta...]}
        self.preload_summary = Signal((dict,))


class SunoDownloader:
    STEM_INDICATORS = [
        "(bass)", "(drums)", "(backing vocal)", "(backing vocals)", "(vocals)", "(instrumental)",
        "(woodwinds)", "(brass)", "(fx)", "(synth)", "(strings)",
        "(percussion)", "(keyboard)", "(guitar)"
    ]

    def __init__(self, manifest=None):
        self.signals = DownloaderSignals()
        self.stop_event = threading.Event()
        self.config = {}
        self.rate_limiter = RateLimiter(0.0)
        # When set, dedupe and post-download bookkeeping use the manifest
        # instead of walking the directory for ID3 tags.
        self.manifest = manifest

    def configure(self, token, directory, max_pages, start_page,
                  organize_by_month, embed_metadata_enabled, prefer_wav, download_delay,
                  filter_settings=None, scan_only=False, target_songs=None, save_lyrics=True,
                  organize_by_track=False, stems_only=False, smart_resume=False, force_rescan=False,
                  organize_by_playlist=False):
        self.config = {
            "token": token,
            "directory": directory,
            "max_pages": max_pages,
            "start_page": start_page,
            "organize_by_month": organize_by_month,
            "embed_metadata": embed_metadata_enabled,
            "save_lyrics": save_lyrics,
            "prefer_wav": prefer_wav,
            "download_delay": max(0.0, float(download_delay)),
            "filter_settings": filter_settings or {},
            "scan_only": scan_only,
            "target_songs": target_songs or [], # List of dicts or UUIDs
            "organize_by_track": organize_by_track,
            "stems_only": stems_only,
            "smart_resume": smart_resume,
            "force_rescan": force_rescan,
            "organize_by_playlist": organize_by_playlist
        }
        self.rate_limiter = RateLimiter(self.config["download_delay"])

    def stop(self):
        self.stop_event.set()

    def is_stopped(self):
        return self.stop_event.is_set()

    def _log(self, message, msg_type="info", thumbnail_data=None):
        """Internal helper to emit log signals."""
        self.signals.log_message.emit(message, msg_type, thumbnail_data)
        if thumbnail_data:
            self.signals.thumbnail_fetched.emit(thumbnail_data, message)

    def run(self):
        self.stop_event.clear()

        token = self.config.get("token", "").strip()

        # Sanitize token: Remove any non-ASCII characters (e.g. ellipsis from copy-paste)
        if token:
            token = re.sub(r'[^\x00-\x7F]+', '', token)

        if not token:
            error_msg = "Token missing; download halted."
            self._log(error_msg, "error")
            self.signals.download_complete.emit(False)
            return

        directory = self.config.get("directory")
        if not directory:
            error_msg = "Download directory not set."
            self._log(error_msg, "error")
            self.signals.download_complete.emit(False)
            return

        if not os.path.exists(directory):
            os.makedirs(directory)

        delay = self.config.get("download_delay", 0)
        if delay > 0:
            self._log(f"Rate limiter enabled: waiting {delay:.2f}s between downloads.", "info")

        scan_only = self.config.get("scan_only", False)
        # Removed: if self.config.get("scan_only"): self._run_scan_only(); return
        # The logic below handles scan_only mode correctly.

        target_songs = self.config.get("target_songs", [])
        filters = self.config.get("filter_settings", {})

        headers = {"Authorization": f"Bearer {token}"}
        if self.manifest is not None:
            existing_uuids = self.manifest.dedupe_set()
        else:
            existing_uuids = get_downloaded_uuids(directory)

        # Shared Subfolder Logic (for both Mode 1 and 2)
        workspace_id = filters.get("workspace_id")
        subfolder_name = None
        do_organize = self.config.get("organize_by_playlist")
        ws_name = filters.get("workspace_name")

        if do_organize and workspace_id and ws_name:
             # If it's a workspace/playlist download, we use the name as subfolder
            subfolder_name = sanitize_filename(ws_name)
            self._log(f"DEBUG: (Pre-Calc) Subfolder set to: {subfolder_name}", "info")

        # Mode 1: Download Specific Songs (from Preload)
        if target_songs:
            self.signals.status_changed.emit(f"Downloading {len(target_songs)} selected songs...")
            self._log(f"Starting download of {len(target_songs)} selected songs...", "info")

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for song_data in target_songs:
                    if self.is_stopped(): break
                    futures.append(
                        executor.submit(
                            self.download_single_song,
                            song_data,
                            directory,
                            headers,
                            token,
                            existing_uuids,
                            self.rate_limiter,
                            subfolder_name
                        )
                    )

                # Wait for futures but check stop event
                total_tasks = len(futures)
                completed_tasks = 0

                for future in futures:
                    if self.is_stopped():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        future.result()
                        completed_tasks += 1
                        if total_tasks > 0:
                            p = int((completed_tasks / total_tasks) * 100)
                            self.signals.progress_updated.emit(p)
                    except Exception as e:
                        import traceback
                        error_msg = f"Download error: {str(e)}\n{traceback.format_exc()}"
                        self._log(error_msg, "error")

            if self.is_stopped():
                self.signals.status_changed.emit("Stopped")
                self._log("Process stopped by user.", "warning")
                self.signals.download_complete.emit(False)
            else:
                self.signals.status_changed.emit("Complete")
                self._log("Process finished successfully.", "success")
                self.signals.download_complete.emit(True)
            return

        # Mode 2: Scan/Download from Feed/Workspace
        self.signals.status_changed.emit("Scanning...")
        self._log("Scanning existing files...", "info")
        self._log(f"Found {len(existing_uuids)} existing songs.", "info")

        # --- URL Selection Logic ---
        workspace_id = filters.get("workspace_id")
        is_public = filters.get("is_public", False)

        params = []
        # Common params
        if filters.get("liked"): params.append("liked=true")
        if filters.get("trashed"): params.append("trashed=true")

        if workspace_id:
            # Workspace/Project Endpoint
            # User correction: Use /api/project/{id} (no /clips, no trailing slash before ?)
            if workspace_id == "default":
                # Assuming default project ID is "default"
                base_url = "https://studio-api.prod.suno.com/api/project/default"
            else:
                # Check if it is a playlist or project
                if filters.get("type") == "playlist":
                     # Playlists might not support pagination, so we'll try without page parameter first
                     base_url = f"https://studio-api.prod.suno.com/api/playlist/{workspace_id}/"
                else:
                     base_url = f"https://studio-api.prod.suno.com/api/project/{workspace_id}"

            self._log(f"Fetching from {filters.get('type', 'Project')}: {filters.get('workspace_name', workspace_id)}", "info")
        elif is_public:
            # Public Feed (v2)
            base_url = "https://studio-api.prod.suno.com/api/feed/v2"
            params.append("is_public=true")
            self._log("Fetching from Public Feed", "info")
        else:
            # My Library (v1) - Default
            base_url = "https://studio-api.prod.suno.com/api/feed/"
            self._log("Fetching from My Library", "info")

        # Append params to base_url
        if params:
            separator = "&" if "?" in base_url else "?"
            base_url += separator + "&".join(params)

        # Check if this is a playlist (playlists might not support pagination)
        is_playlist = filters and filters.get("type") == "playlist"

        # Ensure URL ends with page= for the loop (unless it's a playlist)
        if not is_playlist:
            separator = "&" if "?" in base_url else "?"
            base_url += f"{separator}page="

        subfolder_name = None
        # Only create subfolder if enabled in settings
        do_organize = self.config.get("organize_by_playlist")
        ws_name = filters.get("workspace_name")
        self._log(f"DEBUG: Organize Playlist: {do_organize}, WS Name: {ws_name}, WS ID: {workspace_id}", "info")

        if do_organize and workspace_id and ws_name:
             # If it's a workspace/playlist download, we use the name as subfolder
            subfolder_name = sanitize_filename(ws_name)
            self._log(f"DEBUG: Subfolder set to: {subfolder_name}", "info")
        else:
            self._log("DEBUG: No subfolder will be used.", "info")

        self._log(f"API URL: {base_url}...", "info")

        max_pages = self.config.get("max_pages", 0)
        page_num = self.config.get("start_page", 1)

        success = True
        try:
            self.signals.status_changed.emit("Fetching List...")
            self._log("Fetching song list...", "info")

            # Build UUID cache for duplicate detection.
            if self.config.get("force_rescan"):
                self._log("Force Rescan Active: Skipping dedupe cache.", "warning")
                uuid_cache = set()
            elif self.manifest is not None:
                uuid_cache = self.manifest.dedupe_set()
                self._log(f"Manifest dedupe: {len(uuid_cache)} known UUIDs.", "info")
            else:
                self._log(f"Building UUID cache from: {directory}", "info")
                from sunatra.core.utils import build_uuid_cache
                uuid_cache = build_uuid_cache(directory)
                self._log(f"Found {len(uuid_cache)} existing songs in cache.", "info")

            # Preload summary buckets (only meaningful in scan_only mode).
            preload_summary = {"new": [], "on_disk": [], "missing_on_disk": [], "trashed": []}

            consecutive_skipped_pages = 0
            # Adaptive threshold: scale with library size
            # For small libraries (< 100 songs): 2 pages
            # For medium libraries (100-1000 songs): 5 pages
            # For large libraries (1000-5000 songs): 10 pages
            # For very large libraries (> 5000 songs): 20 pages
            library_size = len(uuid_cache)
            if library_size < 100:
                smart_resume_threshold = 2
            elif library_size < 1000:
                smart_resume_threshold = 5
            elif library_size < 5000:
                smart_resume_threshold = 10
            else:
                smart_resume_threshold = 20

            # Track if we've found ANY new songs yet (to avoid stopping on initial already-downloaded pages)
            found_new_songs = False

            if self.config.get("smart_resume"):
                self._log(f"Smart Resume: Will stop after {smart_resume_threshold} consecutive pages with no new songs (library size: {library_size} songs).", "info")

            with ThreadPoolExecutor(max_workers=3) as executor:
                while not self.is_stopped():
                    if max_pages > 0 and page_num > max_pages:
                        self._log(f"Reached max pages limit ({max_pages}). Stopping.", "info")
                        break

                    self._log(f"Page {page_num}...", "info")
                    # Retry logic for fetching page
                    max_retries = 3
                    for attempt in range(max_retries):
                        if self.is_stopped():
                            break
                        try:
                            # For playlists, don't append page number
                            if is_playlist:
                                url = base_url
                            else:
                                url = f"{base_url}{page_num}"
                            # Increased timeout to 30s and added retry loop
                            r = requests.get(url, headers=headers, timeout=30)


                            # 404 Fallback Logic: Project -> Playlist
                            if r.status_code == 404:
                                if "/api/project/" in base_url:
                                    if "default" in base_url:
                                        self._log("Default Project endpoint 404. Falling back to Main Library (Feed).", "warning")
                                        base_url = "https://studio-api.prod.suno.com/api/feed/"
                                        continue

                                    self._log("Project endpoint 404. Switching to Playlist endpoint...", "warning")
                                    # Regex replace /api/project/ID -> /api/playlist/ID/
                                    base_url = re.sub(r"/api/project/([^?&]+)", r"/api/playlist/\1/", base_url)
                                    continue # Retry immediately with new URL
                                else:
                                    self._log("Error: Resource not found (404).", "error")
                                    success = False
                                    break

                            if r.status_code == 401:
                                self._log("Error: Token expired.", "error")
                                self.signals.error_occurred.emit("Token expired. Please get a new token.")
                                success = False
                                break # Break retry loop, outer loop will also break due to success=False
                            r.raise_for_status()
                            data = r.json()

                            # ZERO ITEMS Fallback (Specific to Default Project)
                            # If we are on the first requested page (usually 1) and we get 0 items from "default" project
                            # It likely means the user expects "My Library" but selected "My Workspace".
                            is_default_project = "project/default" in base_url
                            if is_default_project and (page_num == 1 or page_num == self.config.get("start_page", 1)):
                                # Check if empty result
                                has_items = False
                                if isinstance(data, dict):
                                    if "project_clips" in data and data["project_clips"]: has_items = True
                                    elif "clips" in data and data["clips"]: has_items = True
                                elif isinstance(data, list) and data: has_items = True

                                if not has_items:
                                    self._log("Default Project is empty. Assuming user wants Main Library. switching to Feed...", "warning")
                                    base_url = "https://studio-api.prod.suno.com/api/feed/"
                                    # We need to restart the request with the new URL
                                    continue

                            # Log response structure for playlists
                            if is_playlist:
                                self._log(f"Playlist API Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}", "info")

                            # If successful, break the retry loop
                            break
                        except Exception as exc:
                            if attempt < max_retries - 1:
                                self._log(f"Connection error on page {page_num} (Attempt {attempt+1}/{max_retries}): {exc}. Retrying...", "warning")
                                time.sleep(2)
                                continue
                            else:
                                self._log(f"Request failed after {max_retries} attempts: {exc}", "error")
                                self.signals.error_occurred.emit(f"Network error on page {page_num}: {exc}")
                                success = False
                                break # Break retry loop

                    if not success:
                        break # Break page loop

                    # Handle different API response structures and robustly unwrap clips
                    # 1. Project/Workspace: {"project_clips": [{"clip": {...}}, ...]}
                    # 2. Main Library: [{"id": ...}, ...] or {"clips": [...]}

                    # --- WORKSPACE PARSING LOGIC ---

                    # 1. Identify the list source
                    raw_data = data
                    raw_items = []

                    if isinstance(raw_data, dict):
                        # Try various possible keys for playlist/workspace data
                        if "project_clips" in raw_data:
                            raw_items = raw_data["project_clips"]
                        elif "playlist_clips" in raw_data:
                            raw_items = raw_data["playlist_clips"]
                        elif "clips" in raw_data:
                            raw_items = raw_data["clips"]
                        elif "items" in raw_data:
                            raw_items = raw_data["items"]
                        elif "songs" in raw_data:
                            raw_items = raw_data["songs"]
                        elif "tracks" in raw_data:
                            raw_items = raw_data["tracks"]
                        elif "playlist" in raw_data and isinstance(raw_data["playlist"], dict):
                            # Nested playlist structure
                            playlist_data = raw_data["playlist"]
                            if "playlist_clips" in playlist_data:
                                raw_items = playlist_data["playlist_clips"]
                            elif "clips" in playlist_data:
                                raw_items = playlist_data["clips"]
                            elif "items" in playlist_data:
                                raw_items = playlist_data["items"]
                    elif isinstance(raw_data, list):
                        # Direct list of items
                        raw_items = raw_data

                    if is_playlist:
                        self._log(f"Parsed {len(raw_items)} items from playlist response", "info")
                        if len(raw_items) == 0:
                            self._log(f"WARNING: No items found in playlist response. Response type: {type(data)}, Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}", "warning")

                    # End-of-feed: an empty page means we've exhausted Suno's feed.
                    # Stop here rather than paginating forever against an empty endpoint.
                    if not is_playlist and not raw_items:
                        self._log(f"Page {page_num} returned no items — reached end of feed. Stopping.", "success")
                        break

                    filtered_clips = []

                    # Per-song filtering is delegated to song_passes_filters()
                    # (a pure, unit-tested predicate). The old inline filter-flag
                    # block lived here; it was removed when the logic was extracted.

                    if self.is_stopped(): break

                    skipped_count = 0

                    for item in raw_items:
                        if self.is_stopped(): break

                        # A. UNWRAP STRATEGY
                        if isinstance(item, dict) and "clip" in item:
                            song_data = item["clip"]
                        else:
                            song_data = item

                        if not song_data:
                            continue

                        # Ghost Song Fix (Design Doc Item 1)
                        if not song_data.get("id"):
                             continue

                        title = song_data.get("title", "") or "Unknown Title"
                        if title == "Unknown Title" and not song_data.get("id"):
                             continue

                        is_stem = self._is_stem(song_data)

                        if not song_passes_filters(
                            song_data,
                            filters,
                            stems_only=bool(self.config.get("stems_only")),
                            scan_only=scan_only,
                            is_stem=is_stem,
                        ):
                            continue

                        # Extract UUID
                        uuid = song_data.get("id")

                        # 9. Duplicate Check + Preload Classification
                        if uuid and uuid in uuid_cache:
                            skipped_count += 1
                            # In scan_only mode, classify the skip so the UI
                            # can later offer to re-download files that the
                            # manifest claims exist but disk says don't.
                            if scan_only and self.manifest is not None:
                                if uuid in self.manifest.trashed:
                                    preload_summary["trashed"].append(song_data)
                                else:
                                    entry = self.manifest.entries.get(uuid)
                                    fp = entry.get("filepath", "") if entry else ""
                                    if fp and os.path.exists(fp):
                                        preload_summary["on_disk"].append(song_data)
                                    else:
                                        preload_summary["missing_on_disk"].append(song_data)
                            continue

                        # E. SUCCESS
                        filtered_clips.append(song_data)
                        if scan_only:
                            preload_summary["new"].append(song_data)


                    if skipped_count > 0:
                        self._log(f"Page {page_num}: Skipped {skipped_count} existing songs.", "info")

                    if not filtered_clips:
                        if skipped_count > 0:
                            msg = f"Page {page_num}: All songs skipped (existing). Enable 'Force Rescan' to included."
                            self._log(msg, "warning")
                            self.signals.status_changed.emit("Skipped existing (Check Force Rescan)")
                        else:
                            self._log(f"Page {page_num}: All songs filtered out.", "info")

                    # Track if we found new songs on this page
                    if filtered_clips:
                        found_new_songs = True
                        consecutive_skipped_pages = 0  # Reset counter when we find new songs
                    else:
                        # Only count skipped pages if we've already found some new songs
                        # This prevents stopping on initial pages of already-downloaded content
                        if found_new_songs:
                            consecutive_skipped_pages += 1
                        # If we haven't found any new songs yet, don't count skipped pages
                        # This allows scanning through already-downloaded pages at the start

                    # Smart Resume: Only stop if we've found new songs before, then hit threshold
                    # This ensures we scan past initial already-downloaded pages
                    if self.config.get("smart_resume") and found_new_songs and consecutive_skipped_pages >= smart_resume_threshold:
                        self._log(f"Smart Resume: Found new songs earlier, but no new songs in last {smart_resume_threshold} consecutive pages. Stopping scan.", "success")
                        success = True
                        break

                    if scan_only:
                        for clip in filtered_clips:
                            if self.is_stopped(): break
                            self.signals.song_found.emit(clip)
                    else:
                        futures = []
                        for clip in filtered_clips:
                            if self.is_stopped(): break
                            futures.append(
                                executor.submit(
                                    self.download_single_song,
                                    clip,
                                    directory,
                                    headers,
                                    token,
                                    uuid_cache,
                                    self.rate_limiter,
                                    subfolder_name
                                )
                            )

                        total_page_tasks = len(futures)
                        completed_page_tasks = 0

                        for future in futures:
                            if self.is_stopped():
                                executor.shutdown(wait=False, cancel_futures=True)
                                break
                            try:
                                future.result()
                                completed_page_tasks += 1
                                if total_page_tasks > 0:
                                    p = int((completed_page_tasks / total_page_tasks) * 100)
                                    self.signals.progress_updated.emit(p)
                            except Exception:
                                pass

                    # For playlists, only fetch once (no pagination)
                    if is_playlist:
                        break

                    # Check if stopped before continuing to next page
                    if self.is_stopped():
                        break

                    page_num += 1
                    time.sleep(1)
        except Exception as exc:
            tb = traceback.format_exc()
            self._log(f"Critical Error: {exc}\n{tb}", "error")
            self.signals.error_occurred.emit(f"Critical Error: {exc}")
            success = False

        if self.is_stopped():
            self.signals.status_changed.emit("Stopped")
        elif success:
            self.signals.status_changed.emit("Complete")
        else:
            self.signals.status_changed.emit("Error")

        # Emit the preload summary before download_complete so the UI can
        # render the breakdown banner before re-enabling the buttons.
        if scan_only:
            try:
                self.signals.preload_summary.emit(preload_summary)
            except Exception:
                pass

        self.signals.download_complete.emit(success)

    def fetch_workspaces(self, token):
        """Fetch list of workspaces (projects) using the correct endpoint with pagination."""
        headers = {"Authorization": f"Bearer {token}"}

        # Endpoint provided by user:
        # https://studio-api.prod.suno.com/api/project/me?page=1&sort=created_at&show_trashed=false

        all_projects = []
        page_num = 1

        while True:
            url = f"{GEN_API_BASE}/api/project/me?page={page_num}&sort=created_at&show_trashed=false"

            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    # User confirmed structure: {"projects": [...]}
                    projects = data.get("projects", [])

                    # If no projects on this page, we've reached the end
                    if not projects:
                        break

                    all_projects.extend(projects)
                    page_num += 1
                elif r.status_code == 404:
                    # No more pages
                    break
                else:
                    self._log(f"Failed to fetch projects page {page_num}: {r.status_code} {r.text}", "error")
                    break
            except Exception as e:
                self._log(f"Error fetching projects page {page_num}: {e}", "error")
                break

        return all_projects

    def fetch_playlists(self, token):
        """Fetch list of playlists with pagination."""
        headers = {"Authorization": f"Bearer {token}"}
        # Endpoint: /api/playlist/me?page=1&show_trashed=false&show_sharelist=false

        all_playlists = []
        page_num = 1

        while True:
            url = f"{GEN_API_BASE}/api/playlist/me?page={page_num}&show_trashed=false&show_sharelist=false"

            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    # Structure: {"playlists": [...]}
                    playlists = data.get("playlists", [])

                    # If no playlists on this page, we've reached the end
                    if not playlists:
                        break

                    all_playlists.extend(playlists)
                    page_num += 1
                elif r.status_code == 404:
                    # No more pages
                    break
                else:
                    self._log(f"Failed to fetch playlists page {page_num}: {r.status_code} {r.text}", "error")
                    break
            except Exception as e:
                self._log(f"Error fetching playlists page {page_num}: {e}", "error")
                break

        return all_playlists

    def download_single_song(self, clip, directory, headers, token, existing_uuids, rate_limiter, subfolder_name=None):
        if self.is_stopped():
            return

        uuid = clip.get("id")
        if uuid in existing_uuids:
            self._log(f"Skipping: {clip.get('title') or uuid} (already downloaded)", "info")
            return

        title = clip.get("title") or uuid
        image_url = clip.get("image_url")
        display_name = clip.get("display_name")
        metadata = clip.get("metadata", {})
        prompt = metadata.get("prompt", "")

        # --- REFETCH STRATEGY ---
        # If prompt is missing (common in V5/Covers list view), fetch full details
        if not prompt:
            clip_id = clip.get("id")
            if clip_id:
                try:
                    detail_url = f"https://studio-api.prod.suno.com/api/clip/{clip_id}"
                    # Use the same headers (auth) as the main request
                    r_refetch = requests.get(detail_url, headers=headers, timeout=10)
                    if r_refetch.status_code == 200:
                        full_details = r_refetch.json()
                        metadata = full_details.get("metadata", {})
                        prompt = metadata.get("prompt", "")
                        # Update clip metadata so subsequent logic uses it
                        clip["metadata"] = metadata
                except Exception as e:
                    self._log(f"Failed to refetch prompt for {clip_id}: {e}", "warning")
        # ------------------------
        tags = metadata.get("tags", "")
        created_at = clip.get("created_at", "")
        year = created_at[:4] if created_at else None
        lyrics = metadata.get("lyrics") or metadata.get("text") or prompt
        if lyrics:
            self._log(f"Lyrics found ({len(lyrics)} chars). Start: {lyrics[:30]}...", "info")
        else:
            self._log(f"No lyrics found for {title} in metadata", "warning")

        thumb_data = self.fetch_thumbnail_bytes(image_url) if image_url else None

        # Notify start
        self.signals.song_started.emit(uuid, title, thumb_data, metadata)

        audio_url, file_ext, used_wav = self._resolve_audio_stream(clip, title, headers)
        if not audio_url:
            self._log(f"No usable audio stream for {title}; skipping.", "error")
            self.signals.song_updated.emit(uuid, "Error", 0)
            return

        target_dir = directory

        if subfolder_name:
            try:
                target_dir = os.path.join(directory, subfolder_name)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
            except: pass
        elif self.config.get("organize_by_month") and created_at:
            try:
                month_folder = created_at[:7]
                target_dir = os.path.join(directory, month_folder)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
            except:
                pass

        if self.config.get("organize_by_track") and self._is_stem(clip):
            try:
                # Create a subfolder with the song title (stripped of stem indicators)
                base_title = self._get_base_title(title)
                safe_title = sanitize_filename(base_title)
                target_dir = os.path.join(target_dir, safe_title)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
            except:
                pass

        ext = file_ext or ".mp3"
        fname = sanitize_filename(title) + ext
        # Atomic reservation prevents concurrent download threads from picking
        # the same filename for two distinct UUIDs and silently clobbering each
        # other (manifest ends up with duplicate entries pointing at one file).
        try:
            out_path = reserve_unique_path(os.path.join(target_dir, fname))
        except (RuntimeError, OSError) as exc:
            self._log(f"Failed to reserve filename for {title}: {exc}", "error")
            self.signals.song_updated.emit(uuid, "Error", 0)
            return

        self._log(f"Downloading: {title}", "downloading", thumbnail_data=thumb_data)
        self.signals.song_updated.emit(uuid, "Downloading", 0)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if rate_limiter:
                    rate_limiter.wait()
                with requests.get(audio_url, stream=True, headers=headers, timeout=60) as r_dl:
                    r_dl.raise_for_status()
                    total_size = int(r_dl.headers.get('content-length', 0))
                    downloaded = 0

                    with open(out_path, "wb") as f:
                        for chunk in r_dl.iter_content(chunk_size=8192):
                            if self.is_stopped():
                                f.close()
                                os.remove(out_path)
                                return
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int(downloaded * 100 / total_size)
                                self.signals.song_updated.emit(uuid, "Downloading", percent)
                # Verification: Check file size
                if downloaded < 1024: # Minimum 1KB
                    raise Exception(f"Downloaded file too small ({downloaded} bytes)")
                if total_size > 0 and downloaded < total_size:
                    raise Exception(f"Incomplete download ({downloaded}/{total_size} bytes)")

                break
            except Exception as exc:
                # Cleanup failed file
                if os.path.exists(out_path):
                    try:
                        os.remove(out_path)
                    except: pass

                if attempt < max_retries - 1:
                    self._log(f"  Retry {attempt+1}/{max_retries}: {exc}", "info")
                    time.sleep(2)
                else:
                    self._log(f"Failed: {title} - {exc}", "error")
                    self.signals.song_updated.emit(uuid, "Error", 0)
                    return

        try:
            if lyrics and self.config.get("save_lyrics", True):
                txt_path = os.path.splitext(out_path)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(lyrics)

            # Always embed metadata if enabled, or at least embed lyrics
            if self.config.get("embed_metadata"):
                # Full metadata embedding
                embed_metadata(
                    audio_path=out_path,
                    image_url=image_url,
                    title=title,
                    artist=display_name,
                    genre=tags,
                    year=year,
                    comment=prompt,
                    lyrics=lyrics,
                    uuid=uuid,
                    token=token,
                )
            elif lyrics:
                # Only embed lyrics even if full metadata is disabled
                embed_metadata(
                    audio_path=out_path,
                    lyrics=lyrics,
                    metadata_options={
                        'title': False, 'artist': False, 'genre': False, 'year': False,
                        'comment': False, 'lyrics': True, 'album_art': False, 'uuid': False
                    }
                )

            existing_uuids.add(uuid)
            if self.manifest is not None:
                from sunatra.core.manifest import LOCATION_DOWNLOADS
                self.manifest.add(
                    uuid,
                    title=title or "",
                    artist=display_name or "",
                    filepath=out_path,
                    location=LOCATION_DOWNLOADS,
                )

            # Save Artwork separately (Design Doc Item 3)
            # We want to ensure Windows Explorer shows it.
            if thumb_data:
                try:
                    # 1. Save as {filename}.jpg
                    jpg_path = os.path.splitext(out_path)[0] + ".jpg"
                    if not os.path.exists(jpg_path):
                        with open(jpg_path, "wb") as f_img:
                            f_img.write(thumb_data)

                    # 2. Save as cover.jpg (Folder View)
                    cover_path = os.path.join(os.path.dirname(out_path), "cover.jpg")
                    if not os.path.exists(cover_path):
                         with open(cover_path, "wb") as f_cov:
                            f_cov.write(thumb_data)
                except Exception as ex:
                    self._log(f"Failed to save artwork file: {ex}", "warning")

            self._log(f"✓ {title}", "success", thumbnail_data=thumb_data)
            self.signals.song_finished.emit(uuid, True, out_path)
        except Exception as exc:
            self._log(f"  Metadata error: {exc}", "error")
            self.signals.song_finished.emit(uuid, True, out_path) # Still success even if metadata fails

    def _is_stem(self, song_data):
        """Check if song is a stem."""
        metadata = song_data.get("metadata", {}) or {}
        if metadata is None: metadata = {}
        clip_type = metadata.get("type", "")
        top_type = song_data.get("type", "")
        title = song_data.get("title", "") or ""

        title_lower = title.lower()
        is_stem_title = any(ind in title_lower for ind in self.STEM_INDICATORS)

        return (clip_type in ["gen_stem", "stem"] or
                "stem" in top_type or
                is_stem_title)

    def _get_base_title(self, title):
        """Strip stem indicators from title to get base song name."""
        clean_title = title
        for ind in self.STEM_INDICATORS:
            pattern = re.escape(ind)
            clean_title = re.sub(pattern, "", clean_title, flags=re.IGNORECASE)
        return clean_title.strip()

    def _resolve_audio_stream(self, clip, title, headers):
        prefer_wav = self.config.get("prefer_wav")
        audio_url = clip.get("audio_url")
        extension = ".mp3"
        used_wav = False
        wav_url = self._find_wav_url(clip)
        if prefer_wav and wav_url:
            audio_url = wav_url
            extension = self._extract_extension_from_url(wav_url, default=".wav")
            used_wav = True
        elif prefer_wav:
            # self._log(f"WAV stream unavailable for '{title}'. Requesting conversion...", "info")
            converted = self._fetch_converted_wav(clip, headers)
            if converted:
                audio_url = converted
                extension = self._extract_extension_from_url(converted, default=".wav")
                used_wav = True
            else:
                self._log(f"Conversion failed or timed out for '{title}'. Falling back to MP3.", "error")

        if not audio_url:
            return None, None, False

        if not used_wav:
            extension = self._extract_extension_from_url(audio_url, default=".mp3")

        return audio_url, extension, used_wav

    def _find_wav_url(self, data):
        if isinstance(data, str):
            val = data.strip()
            lowered = val.lower()
            if lowered.startswith("http") and ".wav" in lowered:
                return val
            return None

        if isinstance(data, dict):
            prioritized = (
                "audio_url_wav",
                "wav_url",
                "wav_audio_url",
                "master_wav_url",
                "preview_wav_url",
            )
            for key in prioritized:
                val = data.get(key)
                if isinstance(val, str) and val.lower().startswith("http") and ".wav" in val.lower():
                    return val
            for value in data.values():
                candidate = self._find_wav_url(value)
                if candidate:
                    return candidate

        if isinstance(data, list):
            for entry in data:
                candidate = self._find_wav_url(entry)
                if candidate:
                    return candidate
        return None

    def _fetch_converted_wav(self, clip, headers):
        clip_id = clip.get("id")
        if not clip_id:
            return None
        convert_url = f"{GEN_API_BASE}/api/gen/{clip_id}/convert_wav/"
        # self._log(f"Requesting WAV conversion for '{clip_id}'...", "info")
        try:
            resp = requests.post(convert_url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            self._log(f"Failed to request WAV conversion: {exc}", "error")
            return None
        return self._wait_for_wav_url(clip_id, headers)

    def _wait_for_wav_url(self, clip_id, headers, timeout=120, interval=2):
        deadline = time.monotonic() + timeout
        detail_url = f"https://studio-api.prod.suno.com/api/gen/{clip_id}/wav_file/"
        while time.monotonic() < deadline and not self.is_stopped():
            try:
                resp = requests.get(detail_url, headers=headers, timeout=15)
                if resp.status_code == 404:
                    time.sleep(interval)
                    continue
                resp.raise_for_status()
                data = resp.json()
                wav_url = self._find_wav_url(data)
                if wav_url:
                    return wav_url
            except requests.HTTPError as http_err:
                status = http_err.response.status_code if http_err.response else "?"
                if status != 404:
                    self._log(f"WAV status check failed ({status}): {http_err}", "info")
            except Exception as exc:
                self._log(f"WAV status check failed: {exc}", "info")
            time.sleep(interval)
        if self.is_stopped():
            self._log("WAV polling aborted.", "info")
        else:
            self._log("WAV conversion timed out.", "error")
        return None

    def _extract_extension_from_url(self, url, default=".mp3"):
        try:
            path = urlparse(url).path
            ext = os.path.splitext(path)[1]
            return ext.lower() if ext else default
        except:
            return default

    def fetch_thumbnail_bytes(self, url, size=40):
        try:
            from io import BytesIO

            from PIL import Image
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        except:
            return None

