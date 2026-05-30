import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core.downloader import SunoDownloader

# Helpers and Widgets
from core.utils import truncate_path
from ui.layouts import create_token_dialog
from ui.tooltip import ToolTip
from ui.widgets import Dropdown, EmptyStateWidget, FilterBar, FlowLayout, SongCard


# Stdout Capture for Debug Log
class StdoutCapture:
    def __init__(self, tab_instance):
        self.tab = tab_instance
        try:
            self.original_stdout = sys.stdout if sys.stdout else sys.__stdout__
        except Exception:
            self.original_stdout = sys.__stdout__
        self.buffer = ""

    def write(self, text):
        try:
            if self.original_stdout:
                self.original_stdout.write(text)
                self.original_stdout.flush()
        except Exception:
            pass

        if text and self.tab is not None:
            try:
                self.tab.add_debug_log(text)
            except Exception:
                # Tab destroyed or otherwise unavailable; drop the line.
                self.tab = None

    def flush(self):
        try:
            if self.original_stdout:
                self.original_stdout.flush()
        except Exception:
            pass

    def detach(self):
        """Stop forwarding to the tab; keep tee'd writes to the original stream."""
        self.tab = None

# Cap how many SongCards we render at once during preload. Tk + CTk choke when
# you pack hundreds of widgets in rapid bursts (cards briefly flash at root
# coords during layout, looking like UI escaping the window). All found songs
# still go into preloaded_songs and download on Start; this is purely a render
# throttle. "Show More" reveals the next page.
PRELOAD_RENDER_CAP = 100


class DownloaderTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager, manifest=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.manifest = manifest
        self.downloader = SunoDownloader(manifest=manifest)
        # Preload pagination state — see PRELOAD_RENDER_CAP.
        self._preload_pending = []   # metadata dicts found beyond the render cap
        self._preload_rendered = 0
        self._preload_banner = None
        self._preload_more_btn = None
        # Preload summary state (populated when downloader emits preload_summary).
        self._preload_summary = None
        self._preload_summary_widget = None

        # State
        self.gui_queue = queue.Queue()
        self.queue_items = {} # uuid -> SongCard
        self.preloaded_songs = {} # uuid -> meta
        self.is_preloaded = False
        self.filter_settings = {}
        self.debug_logs = []
        self.debug_window = None

        # Theme Attributes
        self.card_bg = "#181818"

        # Debug Log Capture
        self._stdout_capture = StdoutCapture(self)
        self._original_stdout = sys.stdout
        sys.stdout = self._stdout_capture

        # UI Setup
        self._setup_layout()
        self.load_config()

        # Start GUI Loop
        self.after(100, self._process_gui_queue)


        # Dropdowns
        self._setup_dropdowns()

        # Initial checks
        self.after(500, self.check_initial_path)

    def _setup_layout(self):
        # --- Root Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) # Row 3 is now the list

        # --- 1. Compact Header (Flow Layout) ---
        # "Combine Connection, Scan Settings, and Target into a single unified header"

        self.header_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # We use FlowLayout inside this styled frame
        self.header_flow = FlowLayout(self.header_frame)
        self.header_flow.pack(fill="x", expand=True, padx=5, pady=5)

        # Helper for mini-sections
        def add_section_label(parent, text):
            l = ctk.CTkLabel(parent, text=text, font=("Inter", 11, "bold"), text_color="#94a3b8")
            l.pack(side="left", padx=(0, 8))

        def create_group_frame():
            f = ctk.CTkFrame(self.header_flow, fg_color="transparent")
            return f

        # --- Group 1: Connection ---
        conn_group = create_group_frame()
        add_section_label(conn_group, "Suno Cookie:")

        self.token_var = ctk.StringVar()
        self.token_entry = ctk.CTkEntry(conn_group, textvariable=self.token_var, show="●", width=120, height=24,
                                         fg_color="#1e293b", border_color="#334155",
                                         text_color="#FFFFFF", font=("Inter", 11))
        self.token_entry.pack(side="left", padx=(0, 5))

        ctk.CTkButton(conn_group, text="Get", command=self.get_token_logic, width=40, height=24,
                      fg_color="#334155", hover_color="#475569", font=("Inter", 11),
                      corner_radius=6).pack(side="left")

        self.header_flow.add_widget(conn_group, padx=8, pady=4)

        # Separator
        sep1 = ctk.CTkFrame(self.header_flow, width=1, height=20, fg_color="#334155")
        self.header_flow.add_widget(sep1, padx=4, pady=4)

        # --- Group 2: Settings ---
        settings_group = create_group_frame()

        self.rate_limit_var = ctk.DoubleVar(value=0.5)
        self.start_page_var = ctk.IntVar(value=1)
        self.max_pages_var = ctk.IntVar(value=0)

        # Auto-save triggers
        self.rate_limit_var.trace_add("write", lambda *args: self.save_config())
        self.start_page_var.trace_add("write", lambda *args: self.save_config())
        self.max_pages_var.trace_add("write", lambda *args: self.save_config())

        def add_mini_input(label, var, width=40, tooltip=""):
            ctk.CTkLabel(settings_group, text=label, font=("Inter", 11), text_color="#cbd5e1").pack(side="left", padx=(5, 2))
            e = ctk.CTkEntry(settings_group, textvariable=var, width=width, height=24,
                             fg_color="#1e293b", border_color="#334155", text_color="#FFFFFF", font=("Inter", 11))
            e.pack(side="left")
            if tooltip: ToolTip(e, tooltip)

        add_mini_input("Speed:", self.rate_limit_var, 35, "Delay (s)")
        add_mini_input("Page:", self.start_page_var, 35, "Start Page")
        add_mini_input("Limit:", self.max_pages_var, 35, "Max Pages (0=All)")

        self.header_flow.add_widget(settings_group, padx=8, pady=4)

        # Separator
        sep2 = ctk.CTkFrame(self.header_flow, width=1, height=20, fg_color="#334155")
        self.header_flow.add_widget(sep2, padx=4, pady=4)

        # --- Group 3: Target ---
        target_group = create_group_frame()

        self.workspace_btn = ctk.CTkButton(target_group, text="Workspaces", command=self.open_workspaces, height=24, width=90,
                                           corner_radius=12, fg_color="#334155", hover_color="#475569",
                                           text_color="#e2e8f0", font=("Inter", 11))
        self.workspace_btn.pack(side="left", padx=(0, 5))

        self.playlist_btn = ctk.CTkButton(target_group, text="Playlists", command=self.open_playlists, height=24, width=80,
                                          corner_radius=12, fg_color="#334155", hover_color="#475569",
                                          text_color="#e2e8f0", font=("Inter", 11))
        self.playlist_btn.pack(side="left")

        self.header_flow.add_widget(target_group, padx=8, pady=4)

        # --- 2. Filter Bar (Row 1) ---
        # Keep existing container but reduce padding slightly
        self.filter_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        self.filter_container.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.filter_bar = FilterBar(self.filter_container, self.filter_settings, self.on_filters_applied)
        self.filter_bar.pack(fill="x", padx=10, pady=10) # Reduced padding

        # --- 3. Action Bar (Row 2) ---
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Use FlowLayout for actions too for safety on very small screens?
        # Or just kept simple pack. The user asked for "flex flex-wrap gap-2"

        # Let's use FlowLayout for buttons to ensure wrapping if needed
        btn_flow = FlowLayout(action_frame)
        btn_flow.pack(fill="x")

        self.preload_btn = ctk.CTkButton(btn_flow, text="Preload List", command=self.preload_songs,
                                         height=32, width=100, fg_color="transparent", border_width=1, border_color="#555",
                                         text_color="#B3B3B3", hover_color="#333333", font=("Inter", 12, "bold"),
                                         corner_radius=8)
        # We need to add them to flow, but FlowLayout expects widgets to be children of it usually for packing
        # Actually my FlowLayout implementation doesn't strictly enforce parenting if we pass widget,
        # but place() works relative to parent. So YES, they must be children of btn_flow.
        # Re-parenting buttons to btn_flow
        self.preload_btn = ctk.CTkButton(btn_flow, text="Preload List", command=self.preload_songs,
                                          height=32, width=100, fg_color="transparent", border_width=1, border_color="#555",
                                          text_color="#B3B3B3", hover_color="#333333", font=("Inter", 12, "bold"),
                                          corner_radius=8)

        self.start_btn = ctk.CTkButton(btn_flow, text="Start Download", command=self.start_download_thread,
                                       height=32, width=130, fg_color="#8B5CF6", hover_color="#7C3AED",
                                       font=("Inter", 12, "bold"), corner_radius=8)

        self.stop_btn = ctk.CTkButton(btn_flow, text="Stop", command=self.stop_download,
                                      height=32, width=70, fg_color="#ef4444", hover_color="#b91c1c",
                                      font=("Inter", 12, "bold"), corner_radius=8)
        self.stop_btn.configure(state="disabled")

        btn_flow.add_widget(self.preload_btn, padx=0, pady=0)
        btn_flow.add_widget(self.start_btn, padx=5, pady=0)
        btn_flow.add_widget(self.stop_btn, padx=5, pady=0)

        # --- 4. Song List (Row 3) ---
        self.queue_list_frame = ctk.CTkScrollableFrame(self, fg_color="#181818")
        self.queue_list_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        # Empty State
        self.empty_state = EmptyStateWidget(self.queue_list_frame, theme={})
        self.empty_state.pack(fill="both", expand=True, pady=40)

        # --- 5. Footer (Row 4) ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(footer, text="Ready", text_color="#10b981", font=("Inter", 11))
        self.status_label.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(footer, height=6, progress_color="#8B5CF6")
        self.progress_bar.pack(side="right", fill="x", expand=True, padx=(10, 0))
        self.progress_bar.set(0)


    def load_config(self):
        c = self.config_manager
        # Variables were created by layout helpers
        if hasattr(self, 'token_var'): self.token_var.set(c.get("token", ""))

        # Variables were created by layout helpers
        if hasattr(self, 'token_var'): self.token_var.set(c.get("token", ""))

        # Shared Settings are not loaded into local vars anymore to avoid conflicts
        # They are read directly from config_manager when needed.

        # Inputs
        if hasattr(self, 'rate_limit_var'): self.rate_limit_var.set(c.get("download_delay", 0.5))
        if hasattr(self, 'max_pages_var'): self.max_pages_var.set(c.get("max_pages", 0))
        if hasattr(self, 'start_page_var'): self.start_page_var.set(c.get("start_page", 1))

        # Filters
        self.filter_settings = c.get("filter_settings", {})

        # Update FilterBar UI from loaded settings (Fix for persistence bug)
        if hasattr(self, 'filter_bar'):
             self.filter_bar.set_filters(self.filter_settings)

        # Restore Workspace/Playlist Button Text


        # Restore Workspace/Playlist Button Text
        ws_name = self.filter_settings.get("workspace_name")
        ws_type = self.filter_settings.get("type")

        if ws_name:
            if ws_type == "workspace":
                 if hasattr(self, 'workspace_btn'): self.workspace_btn.configure(text=truncate_path(ws_name, 12))
            elif ws_type == "playlist":
                 if hasattr(self, 'playlist_btn'): self.playlist_btn.configure(text=truncate_path(ws_name, 12))

    def save_config(self):
        c = self.config_manager
        if hasattr(self, 'token_var'): c.set("token", self.token_var.get())
        # Do NOT save shared settings here (path, toggles) - let SettingsTab handle them


        if hasattr(self, 'rate_limit_var'): c.set("download_delay", self.rate_limit_var.get())
        if hasattr(self, 'max_pages_var'): c.set("max_pages", self.max_pages_var.get())
        if hasattr(self, 'start_page_var'): c.set("start_page", self.start_page_var.get())

        c.set("filter_settings", self.filter_settings)
        c.save_config()

    # --- Actions ---
    def get_token_logic(self):
        create_token_dialog(self) # Helper from suno_layout

    def set_token_from_extension(self, token):
        """Called when Chrome extension pushes a new token."""
        if hasattr(self, 'token_var'):
            self.token_var.set(token)
        if hasattr(self, 'extension_status'):
            import time
            ts = time.strftime("%H:%M:%S")
            self.extension_status.configure(
                text=f"🔗 Auto-refreshed ({ts})",
                text_color="#10b981"
            )
        self.save_config()


    def on_filters_applied(self, new_filters):
        self.filter_settings.update(new_filters)
        self.save_config()


    def _setup_dropdowns(self):
        # Dropdown instances
        self.ws_dropdown = Dropdown(self, self._on_workspace_select, width=250, height=300)
        self.pl_dropdown = Dropdown(self, self._on_playlist_select, width=250, height=300)

    def open_workspaces(self):
        # Calculate position relative to button
        x = self.workspace_btn.winfo_rootx()
        y = self.workspace_btn.winfo_rooty() + self.workspace_btn.winfo_height() + 5

        self.ws_dropdown.show(x, y)
        self.ws_dropdown.show_loading()

        threading.Thread(target=self._fetch_workspaces_thread, daemon=True).start()

    def open_playlists(self):
        x = self.playlist_btn.winfo_rootx()
        y = self.playlist_btn.winfo_rooty() + self.playlist_btn.winfo_height() + 5

        self.pl_dropdown.show(x, y)
        self.pl_dropdown.show_loading()

        threading.Thread(target=self._fetch_playlists_thread, daemon=True).start()

    def _fetch_workspaces_thread(self):
        try:
            token = self.token_var.get()
            if not token:
                raise Exception("No token set")

            items = self.downloader.fetch_workspaces(token)
            # Format for dropdown
            dd_items = []
            for item in items:
                count = item.get('clip_count') or item.get('num_tracks') or 0
                dd_items.append({
                    "label": f"{item.get('name')} ({count})",
                    "value": item,
                    "id": item.get('id')
                })

            self.after(0, lambda: self.ws_dropdown.set_items(dd_items))

        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self.ws_dropdown.show_error(msg))

    def _fetch_playlists_thread(self):
        try:
            token = self.token_var.get()
            if not token:
                raise Exception("No token set")

            items = self.downloader.fetch_playlists(token)
            dd_items = []
            for item in items:
                 count = item.get('num_tracks') or item.get('num_total_results') or 0
                 dd_items.append({
                    "label": f"{item.get('name')} ({count})",
                    "value": item,
                    "id": item.get("id")
                 })

            self.after(0, lambda: self.pl_dropdown.set_items(dd_items))

        except Exception as e:
           msg = str(e)
           self.after(0, lambda: self.pl_dropdown.show_error(msg))

    def _on_workspace_select(self, item):
        data = item["value"]
        name = data.get("name", "Unknown")

        self.filter_settings["workspace_id"] = data.get("id")
        self.filter_settings["workspace_name"] = name
        self.filter_settings["type"] = "workspace"
        self.save_config()

        self.workspace_btn.configure(text=truncate_path(name, 12))
        self.playlist_btn.configure(text="Playlists") # Reset other
        self.log(f"Selected Workspace: {name}")

    def _on_playlist_select(self, item):
        data = item["value"]
        name = data.get("name", "Unknown")

        self.filter_settings["workspace_id"] = data.get("id") # Assuming playlists use same ID field for fetch
        self.filter_settings["workspace_name"] = name
        self.filter_settings["type"] = "playlist"
        self.save_config()

        self.playlist_btn.configure(text=truncate_path(name, 12))
        self.workspace_btn.configure(text="Workspaces") # Reset other
        self.log(f"Selected Playlist: {name}")

    def preload_songs(self):
        if not self.token_var.get():
            messagebox.showwarning("Error", "No token set")
            return

        self.is_preloaded = True
        self.preloaded_songs.clear()
        self._reset_preload_render_state()
        self.clear_queue()

        self.update_status("Scanning...", "busy")
        self.toggle_inputs(False) # Enable Stop button
        self.save_config()

        # Configure downloader for SCAN ONLY
        self._configure_downloader(scan_only=True)

        # Connect signals (Required for UI updates)
        self.downloader.signals.download_complete.connect(self.on_download_complete)
        self.downloader.signals.song_found.connect(self.on_song_found)
        self.downloader.signals.song_started.connect(self.on_song_started)
        self.downloader.signals.song_updated.connect(self.on_song_updated)
        self.downloader.signals.song_finished.connect(self.on_song_finished)
        self.downloader.signals.status_changed.connect(lambda msg: self.update_status(msg, "busy"))
        self.downloader.signals.log_message.connect(lambda msg, type, _: self.log(msg, type))
        self.downloader.signals.error_occurred.connect(self._on_downloader_error)
        self.downloader.signals.preload_summary.connect(self._on_preload_summary)

        threading.Thread(target=self.downloader.run, daemon=True).start()

    def _ignore_song(self, uuid):
        """Permanently dismiss a song from the preload list. Removes the card,
        adds the UUID to the manifest's trashed set so it never resurfaces."""
        if self.manifest is None or not uuid:
            return
        meta = self.preloaded_songs.get(uuid, {}) or {}
        title = meta.get("title", "") or ""
        artist = meta.get("display_name", "") or meta.get("artist", "") or ""
        self.manifest.trash(uuid, title=title, artist=artist)
        self.preloaded_songs.pop(uuid, None)
        card = self.queue_items.pop(uuid, None)
        if card is not None:
            try:
                card.destroy()
            except Exception:
                pass

    def _on_preload_summary(self, summary):
        """Cache the summary and schedule rendering on the UI thread."""
        self._preload_summary = summary
        try:
            self.after(0, self._render_preload_summary)
        except Exception:
            pass

    def _render_preload_summary(self):
        summary = self._preload_summary or {}
        new_n = len(summary.get("new", []))
        on_disk_n = len(summary.get("on_disk", []))
        missing_n = len(summary.get("missing_on_disk", []))
        trashed_n = len(summary.get("trashed", []))
        total = new_n + on_disk_n + missing_n + trashed_n

        # Tear down any existing widget — clear_queue may have already done it,
        # but we re-render whenever the summary changes.
        if self._preload_summary_widget is not None and self._preload_summary_widget.winfo_exists():
            try:
                self._preload_summary_widget.destroy()
            except Exception:
                pass
        self._preload_summary_widget = None

        if not total or not self.queue_list_frame.winfo_exists():
            return

        # Build the panel and pack it at the very top of the queue.
        panel = ctk.CTkFrame(self.queue_list_frame, fg_color="#0f172a", corner_radius=8)
        # Pack before the first existing child so it lands above the cards.
        first_child = next(iter(self.queue_list_frame.winfo_children()), None)
        if first_child is not None:
            panel.pack(fill="x", padx=8, pady=(6, 4), before=first_child)
        else:
            panel.pack(fill="x", padx=8, pady=(6, 4))
        self._preload_summary_widget = panel

        header = ctk.CTkLabel(
            panel, text=f"Preload found {total} songs in this scope",
            font=("Inter", 13, "bold"), text_color="#e2e8f0",
        )
        header.pack(anchor="w", padx=12, pady=(8, 2))

        breakdown = ctk.CTkFrame(panel, fg_color="transparent")
        breakdown.pack(fill="x", padx=12, pady=(0, 6))
        for color, label, count in [
            ("#22c55e", "new", new_n),
            ("#94a3b8", "already on disk", on_disk_n),
            ("#fbbf24", "missing on disk", missing_n),
            ("#7f1d1d", "trashed", trashed_n),
        ]:
            chip = ctk.CTkLabel(
                breakdown, text=f"{count} {label}",
                font=("Inter", 11), text_color=color,
            )
            chip.pack(side="left", padx=(0, 12))

        # Action: re-download missing-on-disk entries.
        if missing_n:
            actions = ctk.CTkFrame(panel, fg_color="transparent")
            actions.pack(fill="x", padx=12, pady=(0, 8))
            ctk.CTkButton(
                actions, text=f"Queue {missing_n} missing for re-download",
                fg_color="#fbbf24", hover_color="#f59e0b", text_color="#1f2937",
                font=("Inter", 11, "bold"),
                command=self._requeue_missing_on_disk,
            ).pack(side="left")

    def _requeue_missing_on_disk(self):
        """Drop manifest entries for the missing-on-disk batch (so they're no
        longer dedupe-blocked) and render their cards in the preload list, so
        the user can hit Start Download to re-grab them."""
        if not self._preload_summary or self.manifest is None:
            return
        missing = list(self._preload_summary.get("missing_on_disk", []))
        if not missing:
            return
        uuids = [m.get("id") for m in missing if m.get("id")]
        self.manifest.forget_uuids(uuids)
        # Add them as preload entries so Start Download will include them.
        for meta in missing:
            self._add_song_card(meta)
        # Empty the missing bucket and re-render the summary so the count drops.
        self._preload_summary["missing_on_disk"] = []
        self._render_preload_summary()
        messagebox.showinfo(
            "Queued for Re-download",
            f"Queued {len(uuids)} previously-downloaded songs. "
            "Click Start Download to fetch them.",
        )

    def _on_downloader_error(self, message):
        """Surface downloader errors to the user. Marshalled to the UI thread."""
        def _show():
            self.update_status(message, "error")
            messagebox.showerror("Download Error", message)
        try:
            self.after(0, _show)
        except Exception:
            pass

    def clear_uuid_cache(self):
        try:
             # Just delete the cache file if it exists
            # We need to access library_cache.json path. It's not stored in config, but main passes it.
            # Wait, DownloaderTab doesn't know about cache file path directly unless passed.
            # But the user said "clear cache button to reset UUID cache". That usually means the internal memory cache or the file.
            # Let's assume they mean preventing duplicates.

            # Reset internal preloaded songs
            self.preloaded_songs.clear()
            self.clear_queue()
            messagebox.showinfo("Cache Cleared", "Queue cleared.\nDownload history is based on files in the current folder.\nTo re-download existing songs, enable 'Force Rescan'.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def start_download_thread(self):
        self.save_config()

        target_list = []
        if self.is_preloaded:
            # Iterate the full preloaded_songs dict (which holds every song
            # found, including those beyond the render cap). For each:
            #   - If a card exists and is unchecked, skip it (user opted out).
            #   - Otherwise (no card rendered, or card checked), include it.
            for uuid, meta in self.preloaded_songs.items():
                card = self.queue_items.get(uuid)
                if card is not None and not card.selected_var.get():
                    continue
                target_list.append(meta)

            if not target_list and self.preloaded_songs:
                messagebox.showinfo("Info", "No songs selected.")
                return

        self.update_status("Downloading...", "busy")
        self.toggle_inputs(False)

        if not self.is_preloaded:
            self.clear_queue()

        # Configure downloader
        # If is_preloaded is True, we pass the specific list.
        # If False, we pass None (or empty list) which triggers full scan/download.
        self._configure_downloader(scan_only=False)
        if target_list:
            self.downloader.config["target_songs"] = target_list
            # Disable page limits if we are targeting specific songs (optional, but safer)
            # self.downloader.config["max_pages"] = 0

        # Connect signals
        self.downloader.signals.download_complete.connect(self.on_download_complete)
        self.downloader.signals.song_found.connect(self.on_song_found)
        self.downloader.signals.song_started.connect(self.on_song_started)
        self.downloader.signals.song_updated.connect(self.on_song_updated)
        self.downloader.signals.song_finished.connect(self.on_song_finished)
        self.downloader.signals.progress_updated.connect(self.on_progress_updated)
        self.downloader.signals.error_occurred.connect(self._on_downloader_error)

        threading.Thread(target=self.downloader.run, daemon=True).start()

    def on_progress_updated(self, percent):
        self.gui_queue.put(("progress", percent))

    def stop_download(self):
        self.downloader.stop()
        self.update_status("Stopping...", "busy")
        self.stop_btn.configure(state="disabled", text="Stopping...")

        # Ensure inputs re-enable after a moment if thread doesn't callback fast enough
        # But correctly, the thread should finish and call on_download_complete
        # which calls toggle_inputs(True).
        # We'll rely on on_download_complete, but force a check.
        self.after(2000, lambda: self.check_stop_status())

    def check_stop_status(self):
        if not self.downloader.is_stopped() and self.start_btn._state == "disabled":
             # Still waiting?
             pass
        else:
             # Just in case
             if self.start_btn._state == "disabled" and not self.downloader.is_stopped():
                 # This means thread might have died silently?
                 pass
             elif self.start_btn._state == "disabled":
                 # Re-enable if stuck
                 self.toggle_inputs(True)
                 self.update_status("Stopped", "normal")

    def _configure_downloader(self, scan_only):
        c = self.config_manager
        base_path = os.getcwd()
        default_path = os.path.join(base_path, "Suno_Downloads")
        # Prefer the new downloads_path, fall back to legacy `path` for users
        # whose migration ran but who haven't split paths yet.
        target_dir = c.get("downloads_path") or c.get("path") or default_path

        self.downloader.configure(
            token=self.token_var.get(),
            directory=target_dir,
            max_pages=self.max_pages_var.get(),
            start_page=max(1, self.start_page_var.get()), # Enforce minimum 1
            organize_by_month=c.get("organize", False),
            embed_metadata_enabled=c.get("embed_metadata", True),
            save_lyrics=c.get("save_lyrics", True),
            prefer_wav=c.get("prefer_wav", False),
            download_delay=self.rate_limit_var.get(),
            filter_settings=self.filter_settings,
            organize_by_track=c.get("track_folder", False),
            smart_resume=c.get("smart_resume", False),
            scan_only=scan_only,
            force_rescan=c.get("force_rescan", False),
            organize_by_playlist=c.get("playlist_folder", False)
        )

    # --- GUI Queue Processing ---
    def _process_gui_queue(self):
        try:
            # Process a small batch per tick. Each `add_song` builds a SongCard
            # widget on the main thread; large batches cause visible UI hitching.
            # 15/50ms = ~300/sec, plenty for the typical preload list size.
            count = 0
            while not self.gui_queue.empty() and count < 15:
                msg = self.gui_queue.get_nowait()
                action = msg[0]
                if action == "status":
                    self.status_label.configure(text=msg[1], text_color=msg[2])
                elif action == "add_song":
                    self._add_song_card(msg[1])
                elif action == "update_song":
                    self._update_song_card(msg[1], msg[2], msg[3])
                elif action == "progress":
                    # Update main progress bar
                    percent = msg[1]
                    self.progress_bar.set(percent / 100.0)
                elif action == "log":
                    text = msg[1]
                    self.debug_logs.append(text)
                    # Limit log size
                    if len(self.debug_logs) > 1000:
                        self.debug_logs = self.debug_logs[-800:]

                    if self.debug_window and self.debug_text:
                        self.debug_text.insert("end", text + "\n")
                        if count % 10 == 0: # Auto-scroll occasionally
                            self.debug_text.see("end")

                count += 1
        except queue.Empty:
            pass
        except Exception:
            pass

        try:
            if self.winfo_exists():
                self.after(50, self._process_gui_queue)
        except tk.TclError:
            pass

    def update_status(self, text, state="normal"):
        colors = {"normal": "#10b981", "busy": "#8b5cf6", "error": "#ef4444"}
        self.gui_queue.put(("status", text, colors.get(state, "gray")))

    def log(self, text, level="info"):
        self.gui_queue.put(("log", text))

    def add_debug_log(self, text):
        self.log(text.strip())

    def on_song_found(self, metadata):
        self.gui_queue.put(("add_song", metadata))


    def fetch_thumb(self, uuid, url):
        threading.Thread(target=lambda: self._fetch_thumb_thread(uuid, url), daemon=True).start()

    def _fetch_thumb_thread(self, uuid, url):
        data = self.downloader.fetch_thumbnail_bytes(url)
        if data:
            self.after(0, lambda: self._set_card_thumb(uuid, data))

    def _set_card_thumb(self, uuid, data):
        if uuid in self.queue_items:
             self.queue_items[uuid].set_thumbnail(data)

    def on_song_started(self, uuid, title, thumb_data, metadata):
        # We need to ensure the card exists
        self.after(0, lambda: self._add_song_card(metadata))
        self.gui_queue.put(("update_song", uuid, "Downloading", 0))

    def on_song_updated(self, uuid, status, progress):
        self.gui_queue.put(("update_song", uuid, status, progress))

    def on_song_finished(self, uuid, success, filepath):
        status = "Complete" if success else "Error"
        progress = 100 if success else 0
        self.gui_queue.put(("update_song", uuid, status, progress))

    def _update_song_card(self, uuid, status, progress):
        if uuid in self.queue_items:
            self.queue_items[uuid].set_status(status, progress)

    def on_download_complete(self, success):
        self.toggle_inputs(True)
        self.update_status("Complete" if success else "Stopped", "normal" if success else "error")

    def toggle_inputs(self, enable):
        state = "normal" if enable else "disabled"
        if hasattr(self, 'start_btn'):
            self.start_btn.configure(state=state)
            self.start_btn.configure(text="Start Download" if enable else "Downloading...")
        if hasattr(self, 'preload_btn'):
            self.preload_btn.configure(state=state)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.configure(state="disabled" if enable else "normal", text="Stop")

    def clear_queue(self):
        for w in self.queue_list_frame.winfo_children():
            w.destroy()
        self.queue_items.clear()
        self._reset_preload_render_state()

        # Re-add empty state
        self.empty_state = EmptyStateWidget(self.queue_list_frame, theme={})
        self.empty_state.pack(fill="both", expand=True, pady=40)

    def _reset_preload_render_state(self):
        self._preload_pending = []
        self._preload_rendered = 0
        self._preload_banner = None
        self._preload_more_btn = None
        self._preload_summary = None
        self._preload_summary_widget = None

    def _add_song_card(self, metadata):
        try:
            uuid = metadata.get("id")
            if not uuid:
                return
            # Always remember the song so download includes it, even if we
            # don't render its card (preload cap).
            if self.is_preloaded:
                self.preloaded_songs[uuid] = metadata

            if uuid in self.queue_items:
                return

            # Preload cap: stash overflow, render a banner + Show More button
            # instead of packing more cards. Non-preload (active download) flows
            # are unaffected — we always want to see those.
            if self.is_preloaded and self._preload_rendered >= PRELOAD_RENDER_CAP:
                self._preload_pending.append(metadata)
                self._update_preload_banner()
                return

            # Remove empty state if present
            if hasattr(self, 'empty_state') and self.empty_state.winfo_exists():
                self.empty_state.destroy()

            # Verify frame exists
            if not self.queue_list_frame.winfo_exists():
                print("Error: Queue list frame does not exist!")
                return

            self._render_song_card(metadata)
        except Exception as e:
            print(f"Error adding song card: {e}")
            self.log(f"UI Error: Failed to add card: {e}", "error")

    def _render_song_card(self, metadata):
        """Actually build and pack the SongCard widget. Caller must already
        have decided that rendering is allowed (cap, dedupe, etc)."""
        uuid = metadata.get("id")
        ignore_cb = self._ignore_song if (self.is_preloaded and self.manifest is not None) else None
        card = SongCard(self.queue_list_frame, uuid, metadata.get("title", "Unknown"),
                        metadata=metadata, bg_color="#181818", on_ignore=ignore_cb)
        card.pack(fill="x", pady=2, padx=5)
        self.queue_items[uuid] = card
        if self.is_preloaded:
            self._preload_rendered += 1

        # Defer thumbnail fetching during preload (see preload_songs comment).
        if metadata.get("image_url") and not self.is_preloaded:
            self.fetch_thumb(uuid, metadata.get("image_url"))

    def _update_preload_banner(self):
        """Show/refresh the 'showing N of M' banner at the top of the queue."""
        total = self._preload_rendered + len(self._preload_pending)
        text = (
            f"Showing first {self._preload_rendered} of {total} songs found. "
            f"All {total} will download when you click Start."
        )
        if self._preload_banner is None or not self._preload_banner.winfo_exists():
            self._preload_banner = ctk.CTkLabel(
                self.queue_list_frame, text=text,
                font=("Inter", 11, "bold"), text_color="#fbbf24",
                wraplength=800, justify="left",
            )
            # Force the banner to the top via packing order
            self._preload_banner.pack(fill="x", pady=(4, 2), padx=8, before=next(iter(self.queue_items.values())) if self.queue_items else None)
        else:
            self._preload_banner.configure(text=text)

        if self._preload_pending and (self._preload_more_btn is None or not self._preload_more_btn.winfo_exists()):
            self._preload_more_btn = ctk.CTkButton(
                self.queue_list_frame,
                text=f"Show {min(PRELOAD_RENDER_CAP, len(self._preload_pending))} More",
                fg_color="#8b5cf6", hover_color="#7c3aed", height=28,
                command=self._show_more_preloaded,
            )
            self._preload_more_btn.pack(fill="x", pady=(2, 4), padx=8)
        elif self._preload_pending and self._preload_more_btn is not None:
            self._preload_more_btn.configure(
                text=f"Show {min(PRELOAD_RENDER_CAP, len(self._preload_pending))} More"
            )

    def _show_more_preloaded(self):
        """Render the next batch of pending preload songs."""
        batch = self._preload_pending[:PRELOAD_RENDER_CAP]
        self._preload_pending = self._preload_pending[PRELOAD_RENDER_CAP:]
        # Destroy the More button so it doesn't shadow the new cards in pack
        # order — _update_preload_banner will rebuild it below the cards if
        # there's still pending overflow.
        if self._preload_more_btn is not None and self._preload_more_btn.winfo_exists():
            self._preload_more_btn.destroy()
        self._preload_more_btn = None
        for metadata in batch:
            try:
                self._render_song_card(metadata)
            except Exception as e:
                print(f"Error rendering pending card: {e}")
        self._update_preload_banner()

    def open_debug_window(self):
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.lift()
            return

        self.debug_window = ctk.CTkToplevel(self)
        self.debug_window.title("Debug Log")
        self.debug_window.geometry("800x600")

        self.debug_text = ctk.CTkTextbox(self.debug_window, font=("Consolas", 12))
        self.debug_text.pack(fill="both", expand=True, padx=10, pady=10)

        for l in self.debug_logs:
            self.debug_text.insert("end", l + "\n")

    def check_initial_path(self):
        """Ensure a download path is configured on startup."""
        path = self.config_manager.get("downloads_path") or self.config_manager.get("path", "")
        if not path:
            pass  # Could prompt user to set a path

    def on_close(self):
        self.downloader.stop()
        self._restore_stdout()

    def _restore_stdout(self):
        capture = getattr(self, "_stdout_capture", None)
        if capture is not None:
            capture.detach()
        original = getattr(self, "_original_stdout", None)
        if original is not None and sys.stdout is capture:
            sys.stdout = original

    def destroy(self):
        try:
            self._restore_stdout()
        finally:
            super().destroy()
