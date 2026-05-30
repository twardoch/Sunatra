"""
Downloads tab — shows files currently sitting in the user's `downloads_path`,
sourced from the LibraryManifest. Each row offers Play / Add-to-Library / Trash
actions. The Library tab handles the curated collection separately.
"""

import os
import shutil
from tkinter import messagebox

import customtkinter as ctk

from core.manifest import LOCATION_DOWNLOADS, LOCATION_LIBRARY

# Cap rendered rows per page so a populated manifest (hundreds of entries)
# doesn't block window paint or scroll. Library tab uses the same value.
PAGE_SIZE = 50


class DownloadsTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager, manifest, player_widget=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.manifest = manifest
        self.player_widget = player_widget
        self.current_page = 0
        self._search_query = ""

        self._build_ui()
        # Don't refresh here — main.show_view() refreshes on first navigation,
        # and skipping the init render keeps app startup snappy when the
        # manifest is large.

    # --- UI ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="⬇  Downloads", font=("Inter", 18, "bold"), text_color="#FFFFFF"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=10)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        self._search_entry = ctk.CTkEntry(
            header, textvariable=self._search_var, placeholder_text="Search title or artist...",
            width=240, height=28,
        )
        self._search_entry.grid(row=0, column=1, sticky="w", padx=(10, 10), pady=10)

        self.count_label = ctk.CTkLabel(
            header, text="", font=("Inter", 12), text_color="#94a3b8"
        )
        self.count_label.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=10)

        ctk.CTkButton(
            header, text="Add All to Library", width=140, height=28,
            fg_color="#8b5cf6", hover_color="#7c3aed", font=("Inter", 12),
            command=self._add_all_to_library,
        ).grid(row=0, column=2, sticky="e", padx=(5, 5), pady=10)

        ctk.CTkButton(
            header, text="Forget Missing", width=120, height=28,
            fg_color="#475569", hover_color="#64748b", font=("Inter", 12),
            command=self._forget_all_missing,
        ).grid(row=0, column=3, sticky="e", padx=(5, 5), pady=10)

        ctk.CTkButton(
            header, text="Forget Duplicates", width=130, height=28,
            fg_color="#475569", hover_color="#64748b", font=("Inter", 12),
            command=self._forget_duplicates,
        ).grid(row=0, column=4, sticky="e", padx=(5, 5), pady=10)

        ctk.CTkButton(
            header, text="↻", width=40, height=28,
            fg_color="#334155", hover_color="#475569", font=("Inter", 14),
            command=self.refresh,
        ).grid(row=0, column=5, sticky="e", padx=(5, 15), pady=10)

        # Pagination row (only visible when total > PAGE_SIZE)
        self.page_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.page_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 0))
        self.prev_btn = ctk.CTkButton(
            self.page_bar, text="◀", width=36, height=24,
            fg_color="#334155", hover_color="#475569",
            command=self._prev_page, state="disabled",
        )
        self.prev_btn.pack(side="left", padx=(0, 4))
        self.page_label = ctk.CTkLabel(self.page_bar, text="", font=("Inter", 11), text_color="#94a3b8")
        self.page_label.pack(side="left", padx=4)
        self.next_btn = ctk.CTkButton(
            self.page_bar, text="▶", width=36, height=24,
            fg_color="#334155", hover_color="#475569",
            command=self._next_page, state="disabled",
        )
        self.next_btn.pack(side="left", padx=4)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#0a0a0a", corner_radius=10)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)
        # Row 2 (the list) gets the expanding weight, not row 1 (page bar).
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

    # --- Data ----------------------------------------------------------------

    def refresh(self):
        for child in list(self.list_frame.winfo_children()):
            child.destroy()

        if self.manifest is None:
            self._show_empty("Manifest not initialized.")
            self._update_pager(0)
            return

        entries = self.manifest.by_location(LOCATION_DOWNLOADS)
        total_all = len(entries)

        if self._search_query:
            q = self._search_query
            entries = [
                e for e in entries
                if q in (e.get("title", "") or "").lower()
                or q in (e.get("artist", "") or "").lower()
            ]
        total = len(entries)
        if self._search_query and total != total_all:
            self.count_label.configure(text=f"{total} of {total_all} match")
        else:
            self.count_label.configure(text=f"{total} item{'s' if total != 1 else ''}")

        if not entries:
            if self._search_query:
                self._show_empty(f"No matches for '{self._search_query}'.")
            else:
                self._show_empty("No new downloads. Files moved to Library or trashed appear in their respective tabs.")
            self._update_pager(0)
            return

        # Sort by downloaded_at descending; render only the current page slice.
        entries.sort(key=lambda e: e.get("downloaded_at", ""), reverse=True)
        max_page = max(0, (total - 1) // PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, max_page))
        start = self.current_page * PAGE_SIZE
        page_entries = entries[start:start + PAGE_SIZE]

        for i, entry in enumerate(page_entries):
            self._build_row(self.list_frame, entry, i)

        self._update_pager(total)

    def _update_pager(self, total):
        max_page = max(0, (total - 1) // PAGE_SIZE) if total else 0
        if total <= PAGE_SIZE:
            self.page_bar.grid_remove()
            return
        self.page_bar.grid()
        self.page_label.configure(text=f"Page {self.current_page + 1} of {max_page + 1}  ({total} total)")
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < max_page else "disabled")

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh()

    def _next_page(self):
        self.current_page += 1
        self.refresh()

    def _on_search(self, *_args):
        self._search_query = self._search_var.get().strip().lower()
        self.current_page = 0
        self.refresh()

    def _show_empty(self, msg):
        ctk.CTkLabel(
            self.list_frame, text=msg,
            font=("Inter", 12), text_color="#64748b",
            wraplength=600, justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=40, padx=20)

    def _build_row(self, parent, entry, index):
        uuid = entry.get("uuid")
        filepath = entry.get("filepath", "")
        on_disk = bool(filepath) and os.path.exists(filepath)

        row = ctk.CTkFrame(parent, fg_color="#181818" if index % 2 == 0 else "#1f1f1f", corner_radius=6)
        row.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        # Status dot
        ctk.CTkLabel(
            row, text="●",
            text_color="#22c55e" if on_disk else "#ef4444",
            font=("Inter", 14),
        ).grid(row=0, column=0, padx=(10, 4), pady=8)

        # Title + artist + path
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", padx=4, pady=6)

        title = entry.get("title") or os.path.basename(filepath) or uuid or "(untitled)"
        artist = entry.get("artist") or "Unknown Artist"
        ctk.CTkLabel(info, text=title, anchor="w", font=("Inter", 13, "bold"),
                     text_color="#FFFFFF").pack(anchor="w", fill="x")
        sub = f"{artist}  •  {os.path.basename(filepath) if filepath else '(no file)'}"
        if not on_disk:
            sub += "  •  ⚠ missing on disk"
        ctk.CTkLabel(info, text=sub, anchor="w", font=("Inter", 11),
                     text_color="#94a3b8").pack(anchor="w", fill="x")

        # Buttons
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.grid(row=0, column=2, sticky="e", padx=(4, 10), pady=6)

        if on_disk and self.player_widget is not None:
            ctk.CTkButton(
                btns, text="▶", width=32, height=28,
                fg_color="#334155", hover_color="#475569", font=("Inter", 12),
                command=lambda fp=filepath, e=entry: self._play(fp, e),
            ).pack(side="left", padx=2)

        if on_disk:
            ctk.CTkButton(
                btns, text="↑ Library", width=80, height=28,
                fg_color="#16a34a", hover_color="#15803d", font=("Inter", 11),
                command=lambda u=uuid: self._add_to_library(u),
            ).pack(side="left", padx=2)
        else:
            # File missing — offer Forget so the song can be re-downloaded.
            ctk.CTkButton(
                btns, text="Forget", width=64, height=28,
                fg_color="#475569", hover_color="#64748b", font=("Inter", 11),
                command=lambda u=uuid: self._forget(u),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            btns, text="🗑", width=32, height=28,
            fg_color="#7f1d1d", hover_color="#991b1b", font=("Inter", 12),
            command=lambda u=uuid, fp=filepath: self._trash(u, fp),
        ).pack(side="left", padx=2)

    # --- Actions -------------------------------------------------------------

    def _play(self, filepath, entry):
        if self.player_widget is None or not os.path.exists(filepath):
            return
        try:
            song_data = {
                "filepath": filepath,
                "title": entry.get("title", ""),
                "artist": entry.get("artist", ""),
                "id": entry.get("uuid", ""),
            }
            self.player_widget.playlist = [song_data]
            self.player_widget.play_song_at_index(0)
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))

    def _library_dir(self):
        return (
            self.config_manager.get("library_path")
            or self.config_manager.get("path")
            or ""
        )

    def _add_to_library(self, uuid):
        entry = self.manifest.get(uuid)
        if entry is None:
            messagebox.showerror("Move Error", f"Manifest entry not found for UUID {uuid}.")
            return
        src = entry.get("filepath", "")
        if not src or not os.path.exists(src):
            messagebox.showerror("Move Error", f"Source file missing:\n{src}")
            return

        library_dir = self._library_dir()
        if not library_dir:
            messagebox.showerror(
                "Library not set",
                "Set a Library folder in Settings before moving files.",
            )
            return
        try:
            os.makedirs(library_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Move Error", f"Could not create library folder:\n{e}")
            return

        dst = os.path.join(library_dir, os.path.basename(src))
        # If a file already exists with the same name, append a counter
        if os.path.exists(dst) and os.path.normcase(dst) != os.path.normcase(src):
            base, ext = os.path.splitext(dst)
            i = 2
            while os.path.exists(f"{base} ({i}){ext}"):
                i += 1
            dst = f"{base} ({i}){ext}"

        try:
            shutil.move(src, dst)
        except OSError as e:
            messagebox.showerror("Move Error", f"Could not move file:\n{e}")
            return

        self.manifest.move(uuid, dst, LOCATION_LIBRARY)
        self.refresh()

    def _add_all_to_library(self):
        entries = self.manifest.by_location(LOCATION_DOWNLOADS)
        movable = [e for e in entries if e.get("filepath") and os.path.exists(e["filepath"])]
        if not movable:
            messagebox.showinfo("Nothing to move", "No on-disk downloads to add to Library.")
            return
        if not messagebox.askyesno(
            "Add all to Library",
            f"Move {len(movable)} file{'s' if len(movable) != 1 else ''} from Downloads into your Library folder?",
        ):
            return
        for entry in movable:
            self._add_to_library(entry["uuid"])
        # _add_to_library already refreshes — but call once more as a safety net
        self.refresh()

    def _forget(self, uuid):
        """Drop the manifest entry without trashing — the song becomes
        re-downloadable on the next sync. Distinct from Trash, which is a
        permanent block."""
        if self.manifest is None or not uuid:
            return
        self.manifest.forget(uuid)
        self.refresh()

    def _forget_all_missing(self):
        """Bulk-prune every download-location entry whose file is gone."""
        if self.manifest is None:
            return
        # Count first so we can show a meaningful confirm dialog without
        # touching state.
        candidates = [
            e for e in self.manifest.by_location(LOCATION_DOWNLOADS)
            if not (e.get("filepath") and os.path.exists(e["filepath"]))
        ]
        if not candidates:
            messagebox.showinfo("Forget Missing", "No missing entries to forget.")
            return
        if not messagebox.askyesno(
            "Forget Missing",
            f"Forget {len(candidates)} entries whose files no longer exist?\n\n"
            "These songs will become re-downloadable on the next sync. "
            "Use Trash instead if you want to permanently block them.",
        ):
            return
        removed = self.manifest.prune_missing_at(LOCATION_DOWNLOADS)
        self.refresh()
        messagebox.showinfo(
            "Forget Missing",
            f"Forgot {len(removed)} entries. They can now be re-downloaded.",
        )

    def _forget_duplicates(self):
        """Drop every manifest entry that shares a filepath with another entry,
        and optionally delete the file on disk so the songs re-download cleanly.
        Both entries are dropped (not 'keep one') because we can't tell which
        UUID's audio actually landed on disk after the race."""
        if self.manifest is None:
            return
        dupes = self.manifest.find_duplicate_filepaths(LOCATION_DOWNLOADS)
        if not dupes:
            messagebox.showinfo("Forget Duplicates", "No duplicate filepaths found.")
            return

        all_uuids = [u for uuids in dupes.values() for u in uuids]
        existing_files = [fp for fp in dupes.keys() if os.path.exists(fp)]

        msg = (
            f"Found {len(dupes)} filepath{'s' if len(dupes) != 1 else ''} shared by "
            f"{len(all_uuids)} manifest entries (race condition during download).\n\n"
            f"Drop all {len(all_uuids)} entries so the songs become re-downloadable?"
        )
        if existing_files:
            msg += (
                f"\n\n{len(existing_files)} file{'s' if len(existing_files) != 1 else ''} on disk "
                "will also be deleted (we can't tell which song's audio actually landed)."
            )
        if not messagebox.askyesno("Forget Duplicates", msg):
            return

        deleted_files = 0
        for fp in existing_files:
            try:
                os.remove(fp)
                deleted_files += 1
            except OSError as e:
                print(f"Could not delete duplicate file {fp}: {e}")
        removed = self.manifest.forget_uuids(all_uuids)
        self.refresh()
        messagebox.showinfo(
            "Forget Duplicates",
            f"Dropped {removed} manifest entries and deleted {deleted_files} files. "
            "These songs can now be re-downloaded.",
        )

    def _trash(self, uuid, filepath):
        if not messagebox.askyesno(
            "Trash",
            "Permanently dismiss this song? It will not be re-downloaded.\n"
            "(The file will be deleted from disk if present.)",
        ):
            return
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as e:
                messagebox.showwarning("Delete failed", f"Could not delete file:\n{e}")
        self.manifest.trash(uuid)
        self.refresh()
