import json
import logging
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.utils import open_file, read_song_metadata
from ui.widgets import LibraryRow

logger = logging.getLogger(__name__)

class LibraryTab(ctk.CTkFrame):
    """Library tab for browsing and playing downloaded songs."""

    def __init__(self, parent, config_manager, cache_file=None, tags_file=None, manifest=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.cache_file = cache_file
        self.tags_file = tags_file
        self.manifest = manifest
        self.library_path = self.config_manager.get("library_path") or self.config_manager.get("path", "")

        self.all_songs = []
        self.filtered_songs = []
        self.current_page = 0
        self.tags = {}
        self.active_filters = {"keep": False, "trash": False, "star": False}
        self._load_tags()

        self.cache = {}
        self.scan_queue = queue.Queue()
        self.is_scanning = False
        self._load_cache()

        self.player_widget = None
        self.song_cards = {} # uuid -> SongCard widget

        # Selection State
        self.selected_rows = []
        self.last_selected_row = None

        self._setup_ui()

        # Start queue processing
        self._process_scan_queue()

        # Initial Refresh
        self.after(500, self.refresh_library)

    def _setup_ui(self):
        # Toolbar
        self.toolbar = ctk.CTkFrame(self, height=50, fg_color="transparent")
        self.toolbar.pack(fill="x", padx=10, pady=(10, 5))

        # Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        self.search_entry = ctk.CTkEntry(self.toolbar, textvariable=self.search_var,
                                         placeholder_text="Search Title, Artist, Genre...",
                                         width=250, font=("Inter", 12),
                                         fg_color="#272727", border_color="#333333",
                                         text_color="#FFFFFF",
                                         placeholder_text_color="#B3B3B3")
        self.search_entry.pack(side="left", padx=(0, 10))

        # Pill / Chip Filter Buttons
        self.filter_btns = {}
        filters = [("👍 Liked", "keep", "#22c55e"), ("⭐ Starred", "star", "#eab308"), ("🗑️ Trash", "trash", "#ef4444")]

        for label, tag, color in filters:
            btn = ctk.CTkButton(self.toolbar, text=label, width=80, height=28,
                                corner_radius=14,
                                fg_color="#333333", border_width=0,
                                text_color="#B3B3B3", hover_color="#444444",
                                font=("Inter", 11),
                                command=lambda t=tag, c=color: self.toggle_filter(t, c))
            btn.pack(side="left", padx=3)
            self.filter_btns[tag] = (btn, color)

        # Refresh
        self.refresh_btn = ctk.CTkButton(self.toolbar, text="🔄", width=36, height=28,
                                         corner_radius=14, fg_color="#333333",
                                         hover_color="#444444",
                                         command=self.refresh_library)
        self.refresh_btn.pack(side="right", padx=5)

        # Change Folder
        ctk.CTkButton(self.toolbar, text="📂", width=36, height=28,
                      corner_radius=14, fg_color="#333333",
                      hover_color="#444444",
                      command=self.change_download_folder).pack(side="right", padx=5)

        # Forget Missing — drops manifest entries whose files are gone, so
        # those songs become re-downloadable. Distinct from Trash (permanent
        # block).
        ctk.CTkButton(self.toolbar, text="Forget Missing", width=120, height=28,
                      corner_radius=14, fg_color="#475569",
                      hover_color="#64748b", text_color="#FFFFFF",
                      font=("Inter", 11),
                      command=self.forget_missing).pack(side="right", padx=5)

        # Rebuild — scans library_path for SUNO_UUID-tagged files and adds
        # them to the manifest (or updates filepath if the file moved into a
        # subfolder). Use after manual file moves or after deleting the
        # manifest.
        ctk.CTkButton(self.toolbar, text="Rebuild from Disk", width=130, height=28,
                      corner_radius=14, fg_color="#475569",
                      hover_color="#64748b", text_color="#FFFFFF",
                      font=("Inter", 11),
                      command=self.rebuild_from_disk).pack(side="right", padx=5)

        # Pagination Controls
        self.page_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.page_frame.pack(side="right", padx=10)

        self.prev_btn = ctk.CTkButton(self.page_frame, text="<", width=28, height=28,
                                      corner_radius=14, fg_color="#333333",
                                      command=self.prev_page, state="disabled")
        self.prev_btn.pack(side="left", padx=2)

        self.page_label = ctk.CTkLabel(self.page_frame, text="0 / 0", width=50,
                                       font=("Inter", 11), text_color="#B3B3B3")
        self.page_label.pack(side="left", padx=5)

        self.next_btn = ctk.CTkButton(self.page_frame, text=">", width=28, height=28,
                                      corner_radius=14, fg_color="#333333",
                                      command=self.next_page, state="disabled")
        self.next_btn.pack(side="left", padx=2)

        # Stat Label
        self.count_label = ctk.CTkLabel(self.toolbar, text="0 songs", width=80,
                                        font=("Inter", 11), text_color="#B3B3B3")
        self.count_label.pack(side="right", padx=5)

        # --- Data Grid Header (no visible borders, subtle bottom line) ---
        self.header_frame = ctk.CTkFrame(self, height=30, fg_color="transparent", corner_radius=0)
        self.header_frame.pack(fill="x", padx=10, pady=(5, 0))

        # Configure Header Layout (Matches LibraryRow exactly)
        self.header_frame.grid_columnconfigure(0, weight=3, minsize=200)  # Title
        self.header_frame.grid_columnconfigure(1, weight=2, minsize=150)  # Artist
        self.header_frame.grid_columnconfigure(2, weight=2, minsize=150)  # Genre
        self.header_frame.grid_columnconfigure(3, weight=1, minsize=80)   # BPM
        self.header_frame.grid_columnconfigure(4, weight=1, minsize=80)   # Duration

        headers = ["Title", "Artist", "Genre", "BPM", "Duration"]
        for idx, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.header_frame, text=text,
                               font=("Inter", 11, "bold"), text_color="#B3B3B3")
            anchor = "w" if idx < 3 else "center" if idx == 3 else "e"
            padx = (10, 5) if idx == 0 else (5, 10) if idx == 4 else 5
            lbl.configure(anchor=anchor)
            lbl.grid(row=0, column=idx, sticky="ew", padx=padx, pady=5)

        # Subtle separator line under header
        ctk.CTkFrame(self, height=1, fg_color="#333333").pack(fill="x", padx=10)

        # Song List Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#181818")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Empty State
        self.empty_state = ctk.CTkLabel(self.scroll_frame,
                                        text="No songs found.\nCheck your folder or download some!",
                                        font=("Inter", 14), text_color="#B3B3B3")

    def _load_tags(self):
        if self.tags_file and os.path.exists(self.tags_file):
            try:
                with open(self.tags_file, encoding='utf-8') as f:
                    self.tags = json.load(f)
            except Exception:
                self.tags = {}

    def change_download_folder(self):
        new_dir = filedialog.askdirectory(initialdir=self.library_path, title="Select Library Folder")
        if new_dir:
            self.library_path = new_dir
            self.config_manager.set("library_path", new_dir)
            self.refresh_library()
            messagebox.showinfo("Folder Changed", f"Library folder updated to:\n{new_dir}")
        else:
            logger.debug("No folder selected, cancelled")

    def _load_cache(self):
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, encoding='utf-8') as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def _save_cache(self):
        if self.cache_file:
             try:
                 with open(self.cache_file, 'w', encoding='utf-8') as f:
                     json.dump(self.cache, f)
             except Exception:
                 pass

    def refresh_library(self):
        """Scan the download folder and reload the song list."""
        if self.is_scanning:
            return

        try:
            self.all_songs = []
            self.filtered_songs = []

            if hasattr(self, '_pending_render') and self._pending_render:
                self.after_cancel(self._pending_render)
                self._pending_render = None

            self.render_page()

            self.library_path = self.config_manager.get("library_path") or self.config_manager.get("path", "")

            if not self.library_path or not os.path.exists(self.library_path):
                 default_path = os.path.join(os.getcwd(), "Suno_Downloads")
                 if os.path.exists(default_path):
                     self.library_path = default_path
                 else:
                     return

            logger.debug("Starting scan of: %s", self.library_path)
            self.is_scanning = True
            self.refresh_btn.configure(state="disabled")
            self.count_label.configure(text="Scanning...")

            self._process_scan_queue()
            threading.Thread(target=self._scan_thread, daemon=True).start()
        except Exception as e:
            logger.error("Refresh error: %s", e)
            self.is_scanning = False
            self.refresh_btn.configure(state="normal")

    def _garbage_collect_widgets(self, widgets):
        # Destroy in chunks
        chunk = widgets[:50]
        remainder = widgets[50:]

        for w in chunk:
            try:
                if w.winfo_exists(): w.destroy()
            except: pass

        if remainder:
            self.after(50, lambda: self._garbage_collect_widgets(remainder))

    def _scan_thread(self):
        """Background thread that walks the download folder and reads metadata."""
        new_songs = []
        count = 0
        try:
             if not os.path.exists(self.library_path):
                 self.scan_queue.put(("done", None))
                 return

             for root, _dirs, files in os.walk(self.library_path):
                for file in files:
                    if file.lower().endswith(('.mp3', '.wav')):
                        filepath = os.path.join(root, file)
                        try:
                            mtime = os.path.getmtime(filepath)
                            cached = self.cache.get(filepath)

                            if cached and cached.get('mtime') == mtime:
                                song_data = cached
                            else:
                                song_data = read_song_metadata(filepath)
                                if song_data:
                                    song_data['mtime'] = mtime
                                    self.cache[filepath] = song_data

                            if song_data:
                                new_songs.append(song_data)
                                count += 1
                                if len(new_songs) >= 10:
                                    self.scan_queue.put(("batch", list(new_songs)))
                                    new_songs = []
                                    time.sleep(0.02)
                        except Exception as e:
                            logger.warning("Error processing %s: %s", file, e)

             if new_songs:
                self.scan_queue.put(("batch", new_songs))

             logger.debug("Scan complete, %d files processed", count)
             self.scan_queue.put(("done", None))
             self._save_cache()

        except Exception as e:
            logger.error("Error in scan thread: %s", e, exc_info=True)
            self.scan_queue.put(("done", None))

    def _process_scan_queue(self):
        """Consume scan results from the background thread and update UI."""
        try:
            while not self.scan_queue.empty():
                try:
                    msg_type, data = self.scan_queue.get_nowait()
                except queue.Empty:
                    break

                if msg_type == "batch":
                    self.all_songs.extend(data)
                    self.count_label.configure(text=f"Found {len(self.all_songs)}...")

                elif msg_type == "done":
                    self.is_scanning = False
                    self.refresh_btn.configure(state="normal")
                    self.all_songs.sort(key=lambda x: x['date'], reverse=True)
                    self.filtered_songs = list(self.all_songs)
                    self.current_page = 0
                    self.render_page()

        except Exception as e:
            logger.error("Error in _process_scan_queue: %s", e, exc_info=True)

        if self.is_scanning or not self.scan_queue.empty():
            self.after(50, self._process_scan_queue)

    def render_page(self):
        """Render the current page of songs in the library view."""
        # Clear existing widgets safely
        try:
            old_widgets = list(self.song_cards.values())
            for w in old_widgets:
                try:
                    if w.winfo_exists():
                        w.pack_forget()
                except Exception:
                    pass

            self.song_cards.clear()

            if old_widgets:
                self.after(100, lambda: self._destroy_widgets(old_widgets))
        except Exception as e:
            logger.warning("Error clearing widgets: %s", e)

        # Calculate page slice
        total = len(self.filtered_songs)
        per_page = 50
        max_page = max(0, (total - 1) // per_page)
        self.current_page = max(0, min(self.current_page, max_page))

        start = self.current_page * per_page
        end = start + per_page
        page_items = self.filtered_songs[start:end]

        # Empty state
        if total == 0:
            if hasattr(self, 'empty_state'): self.empty_state.pack(pady=40)
            self.count_label.configure(text="0 songs")
            self.page_label.configure(text="0 / 0")
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return
        else:
            if hasattr(self, 'empty_state') and self.empty_state.winfo_exists():
                self.empty_state.pack_forget()

        # Render rows
        for i, song in enumerate(page_items):
            if 'title' in song:
                from core.utils import clean_title
                song['title'] = clean_title(song['title'])
            self._add_row(self.scroll_frame, song, start + i)

        # Update controls
        self.count_label.configure(text=f"{total} songs")
        self.page_label.configure(text=f"{self.current_page} / {max_page}")
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < max_page else "disabled")

    def _destroy_widgets(self, widgets):
        """Safely destroy widgets in a delayed callback."""
        for w in widgets:
            try:
                if w.winfo_exists():
                    w.destroy()
            except Exception:
                pass

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        total = len(self.filtered_songs)
        max_page = (total - 1) // 50
        if self.current_page < max_page:
            self.current_page += 1
            self.render_page()

    def _add_row(self, parent, data, index):
        # Odd row check for striping
        odd = (index % 2 == 1)

        try:
            row = LibraryRow(parent, data, on_play=self.play_song_data, on_menu=self.show_context_menu, odd_row=odd, on_click=self.on_row_click)
            row.pack(fill="x", pady=0)

            uuid = data.get("id") or str(hash(data.get("filepath")))
            if "id" in data:
                self.song_cards[data["id"]] = row
            else:
                self.song_cards[uuid] = row
        except Exception as e:
            logger.warning("Error adding row: %s", e)

    def play_song_data(self, data):
        if data:
            self.play_song(data)

    def show_context_menu(self, event, data):
        try:
             # Check selection count logic
             count = len(self.selected_rows)

             # Logic for right-click on selection
             clicked_path = data.get("filepath")
             in_selection = any(r.data.get("filepath") == clicked_path for r in self.selected_rows)

             menu = tk.Menu(self, tearoff=0)

             if count > 1 and in_selection:
                 menu.add_command(label=f"📋 Copy {count} files (Ctrl+C)", command=self.copy_selection)
                 menu.add_separator()
                 # Future: Batch Delete
             else:
                 menu.add_command(label="▶ Play", command=lambda: self.play_song_data(data))
                 menu.add_separator()
                 menu.add_command(label="📋 Copy File (Ctrl+C)", command=self.copy_selection)

             menu.add_command(label="📂 Show in Explorer", command=lambda: self.show_in_explorer(data.get("filepath")))
             menu.add_command(label="✏️ Edit Tags", command=lambda: self.edit_metadata(data))
             menu.add_command(label="📓 Save Prompt to Vault", command=lambda: self.save_prompt_to_vault(data))
             menu.add_separator()
             menu.add_command(label="🗑️ Delete", command=lambda: self.delete_song(data))

             menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            logger.warning("Context menu error: %s", e)

    def edit_metadata(self, data):
        """Open metadata editor dialog."""
        try:
            from ui.metadata_editor import MetadataEditorDialog

            def on_save(updated_data):
                # Refresh library to show updated metadata
                self.refresh_library()

            MetadataEditorDialog(self, data, on_save_callback=on_save)
        except Exception as e:
            logger.error("Error opening metadata editor: %s", e)
            messagebox.showerror("Error", f"Failed to open editor: {e}")

    def save_prompt_to_vault(self, data):
        """Save song prompt to Vault."""
        prompt_text = data.get("prompt", "")
        if not prompt_text:
            # Try to read from file if missing in cache
            if "filepath" in data:
                from core.utils import read_song_metadata
                full_data = read_song_metadata(data["filepath"])
                prompt_text = full_data.get("prompt", "")

        if not prompt_text:
            messagebox.showinfo("Info", "No prompt found for this song.")
            return

        # Ask for title
        data.get("title", "My Prompt")
        dialog = ctk.CTkInputDialog(text="Enter a title for this prompt:", title="Save to Vault")
        title = dialog.get_input()

        if title:
            try:
                from ui.vault import PromptManager
                manager = PromptManager()
                # Extract tags (Genre)
                tags = data.get("genre", "")
                manager.add_prompt(title, prompt_text, tags)

                # Show toast/message
                # We don't have a toast widget, use active label or messagebox
                # Making a non-blocking label or just a message box
                # Design doc said "Toast notification", standard messagebox is safest for now
                messagebox.showinfo("Saved", "Prompt saved to Vault!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save to vault: {e}")

    def show_in_explorer(self, filepath):
        if filepath and os.path.exists(filepath):
            try:
                subprocess.run(['explorer', '/select,', os.path.normpath(filepath)])
            except:
                open_file(os.path.dirname(filepath))

    def delete_song(self, data):
        path = data.get("filepath")
        if not path or not os.path.exists(path): return

        if messagebox.askyesno("Delete", f"Are you sure you want to delete:\\n{data.get('title')}?"):
            try:
                os.remove(path)
                # Remove from UI
                self.refresh_library()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete: {e}")

    def _refresh_list(self):
        """Re-render the current page after filtering."""
        self.current_page = 0
        self.render_page()

    def play_song(self, song_input):
        if not self.player_widget:
            return

        # Determine if song_input is dict or string (filepath)
        selected_song = None
        if isinstance(song_input, dict):
            selected_song = song_input
        elif isinstance(song_input, str):
            # It's a filepath string, find it in all_songs
            for s in self.all_songs:
                if s.get('filepath') == song_input:
                    selected_song = s
                    break

        if not selected_song:
            # Last resort: play it directly if it's a string
            if isinstance(song_input, str) and os.path.exists(song_input):
                self.player_widget.play_file(song_input)
            return

        # Set playlist context and play
        try:
            # Find index in filtered list
            index = self.filtered_songs.index(selected_song)

            # Call player directly instead of using events
            if self.player_widget and hasattr(self.player_widget, 'set_playlist'):
                self.player_widget.set_playlist(self.filtered_songs, index)
            else:
                # Fallback: play single file
                filepath = selected_song.get('filepath', '')
                self.player_widget.play_file(filepath)

        except ValueError:
            # Not in filtered list, play single file
            filepath = selected_song.get('filepath', '')
            if self.player_widget:
                self.player_widget.play_file(filepath)

    def on_search(self, *args):
        query = self.search_var.get().lower()
        active_tags = [t for t, active in self.active_filters.items() if active]

        candidates = self.all_songs

        # Tag filter
        if active_tags:
            filtered = []
            for song in candidates:
                uuid = song.get('id') or song.get('filepath')
                tag = self.tags.get(uuid)
                if tag in active_tags:
                    filtered.append(song)
            candidates = filtered

        # Text filter
        if query:
            self.filtered_songs = [
                s for s in candidates
                if query in s.get('title', '').lower() or query in s.get('artist', '').lower()
            ]
        else:
            self.filtered_songs = list(candidates)

        self._refresh_list()

    def toggle_filter(self, tag, color):
        self.active_filters[tag] = not self.active_filters[tag]

        btn, active_color = self.filter_btns[tag]
        if self.active_filters[tag]:
            btn.configure(fg_color=active_color, text_color="white")
        else:
            btn.configure(fg_color="transparent", text_color="gray")

        self.on_search()

    def select_song(self, filepath):
        # Used by Main to highlight currently playing song
        # TODO: Implement scrolling to song card if visible
        pass

    def rebuild_from_disk(self):
        """Walk library_path, ID3-read every audio file, and reconcile the
        manifest: add unknown UUIDs and update filepaths for UUIDs that have
        moved (e.g., into a subfolder)."""
        if self.manifest is None:
            messagebox.showinfo("Rebuild", "Manifest not initialized.")
            return
        if not self.library_path or not os.path.isdir(self.library_path):
            messagebox.showerror("Rebuild", f"Library folder not found:\n{self.library_path}")
            return
        from core.manifest import LOCATION_LIBRARY
        result = self.manifest.upsert_from_disk(self.library_path, LOCATION_LIBRARY)
        self.refresh_library()
        messagebox.showinfo(
            "Rebuild from Disk",
            f"Scanned {result['scanned']} file(s).\n"
            f"Added {result['added']} new manifest entries.\n"
            f"Updated paths for {result['updated']} moved entries.",
        )

    def forget_missing(self):
        """Drop every library-location manifest entry whose file is gone, so
        those songs become re-downloadable. Common after manually deleting
        files or moving the library folder."""
        if self.manifest is None:
            messagebox.showinfo("Forget Missing", "Manifest not initialized.")
            return
        from core.manifest import LOCATION_LIBRARY
        candidates = [
            e for e in self.manifest.by_location(LOCATION_LIBRARY)
            if not (e.get("filepath") and os.path.exists(e["filepath"]))
        ]
        if not candidates:
            messagebox.showinfo("Forget Missing", "No missing library entries to forget.")
            return
        if not messagebox.askyesno(
            "Forget Missing",
            f"Forget {len(candidates)} library entries whose files no longer exist?\n\n"
            "These songs will become re-downloadable on the next sync. "
            "Trashed UUIDs (permanent dismissals) are not affected.",
        ):
            return
        removed = self.manifest.prune_missing_at(LOCATION_LIBRARY)
        self.refresh_library()
        messagebox.showinfo(
            "Forget Missing",
            f"Forgot {len(removed)} library entries. They can now be re-downloaded.",
        )

    def open_download_folder(self):
        # Fetch fresh path from config
        path = self.config_manager.get("library_path") or self.config_manager.get("path", "")
        if path and os.path.exists(path):
            open_file(path)
        else:
            logger.warning("Library path invalid or not set: %s", path)

    def reload_tags(self):
        self._load_tags()
        self.on_search()

    # --- Batch Selection Logic ---
    def on_row_click(self, event, data, row_widget):
        ctrl_pressed = (event.state & 0x4) != 0
        shift_pressed = (event.state & 0x1) != 0

        if not ctrl_pressed and not shift_pressed:
            self.deselect_all()
            self.set_row_selected(row_widget, True)
            self.last_selected_row = row_widget
        elif ctrl_pressed:
            is_sel = row_widget.is_selected
            self.set_row_selected(row_widget, not is_sel)
            self.last_selected_row = row_widget
        elif shift_pressed:
             if self.last_selected_row and self.last_selected_row != row_widget:
                 rows = [w for w in self.scroll_frame.winfo_children() if isinstance(w, LibraryRow)]
                 try:
                     start_idx = rows.index(self.last_selected_row)
                     end_idx = rows.index(row_widget)

                     if start_idx > end_idx: start_idx, end_idx = end_idx, start_idx

                     for i in range(start_idx, end_idx + 1):
                         self.set_row_selected(rows[i], True)

                 except ValueError:
                     self.set_row_selected(row_widget, True)
                     self.last_selected_row = row_widget
             else:
                 self.set_row_selected(row_widget, True)
                 self.last_selected_row = row_widget

    def set_row_selected(self, row, selected):
        row.set_selected(selected)
        if selected:
            if row not in self.selected_rows:
                self.selected_rows.append(row)
        else:
            if row in self.selected_rows:
                self.selected_rows.remove(row)

    def deselect_all(self, event=None):
        for row in self.selected_rows:
            if row.winfo_exists():
                row.set_selected(False)
        self.selected_rows.clear()

    def select_all(self, event=None):
        if hasattr(self, 'scroll_frame'):
            rows = [w for w in self.scroll_frame.winfo_children() if isinstance(w, LibraryRow)]
            for row in rows:
                self.set_row_selected(row, True)

    def copy_selection(self, event=None):
        if not self.selected_rows: return

        filepaths = [r.data.get('filepath') for r in self.selected_rows if r.data.get('filepath')]
        # Filter existing
        filepaths = [fp.replace("/", "\\") for fp in filepaths if os.path.exists(fp)]

        if not filepaths: return

        try:
            from core.utils import copy_files_to_clipboard
            if copy_files_to_clipboard(filepaths):
                messagebox.showinfo("Copied", f"Copied {len(filepaths)} files to clipboard.")
            else:
                 import pyperclip
                 pyperclip.copy("\n".join(filepaths))
                 messagebox.showinfo("Copied", f"Copied paths of {len(filepaths)} files to clipboard (File copy not supported).")
        except Exception as e:
            messagebox.showerror("Error", f"Copy failed: {e}")
