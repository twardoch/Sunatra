"""
Ignored tab — lists every UUID in the manifest's trashed set with title/artist
context (when known) and a Restore action. Trashed UUIDs are permanently
blocked from re-download until restored.
"""

import customtkinter as ctk

PAGE_SIZE = 50


class IgnoredTab(ctk.CTkFrame):
    def __init__(self, parent, manifest, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.manifest = manifest
        self.current_page = 0
        self._build_ui()
        # main.show_view() refreshes on first navigation; skipping the init
        # render keeps app startup snappy when many UUIDs are trashed.

    # --- UI ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="🚫  Ignored", font=("Inter", 18, "bold"), text_color="#FFFFFF",
        ).grid(row=0, column=0, sticky="w", padx=15, pady=10)

        self.count_label = ctk.CTkLabel(
            header, text="", font=("Inter", 12), text_color="#94a3b8",
        )
        self.count_label.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        ctk.CTkButton(
            header, text="↻", width=40, height=28,
            fg_color="#334155", hover_color="#475569", font=("Inter", 14),
            command=self.refresh,
        ).grid(row=0, column=2, sticky="e", padx=(5, 15), pady=10)

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

        self.help_label = ctk.CTkLabel(
            self, text="Click 🚫 on any preload row to ignore a song. Restore here to allow re-download.",
            text_color="#64748b", font=("Inter", 11), wraplength=800, justify="left",
        )
        self.help_label.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 10))

        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

    # --- Data ----------------------------------------------------------------

    def refresh(self):
        for child in list(self.list_frame.winfo_children()):
            child.destroy()

        if self.manifest is None:
            self._empty("Manifest not initialized.")
            self._update_pager(0)
            return

        entries = self.manifest.trashed_entries()
        n = len(entries)
        self.count_label.configure(text=f"{n} item{'s' if n != 1 else ''}")

        if not entries:
            self._empty("Nothing ignored. The Ignore button (🚫) on a preload row sends songs here.")
            self._update_pager(0)
            return

        entries.sort(key=lambda e: e.get("trashed_at", ""), reverse=True)
        max_page = max(0, (n - 1) // PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, max_page))
        start = self.current_page * PAGE_SIZE
        page_entries = entries[start:start + PAGE_SIZE]

        for i, entry in enumerate(page_entries):
            self._row(self.list_frame, entry, i)

        self._update_pager(n)

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

    def _empty(self, msg):
        ctk.CTkLabel(
            self.list_frame, text=msg,
            font=("Inter", 12), text_color="#64748b",
            wraplength=600, justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=40, padx=20)

    def _row(self, parent, entry, index):
        uuid = entry.get("uuid", "")
        title = entry.get("title") or ""
        artist = entry.get("artist") or ""

        row = ctk.CTkFrame(parent, fg_color="#181818" if index % 2 == 0 else "#1f1f1f", corner_radius=6)
        row.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
        row.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        display_title = title or uuid or "(untitled)"
        ctk.CTkLabel(
            info, text=display_title, anchor="w", font=("Inter", 13, "bold"),
            text_color="#FFFFFF",
        ).pack(anchor="w", fill="x")

        sub_parts = []
        if artist:
            sub_parts.append(artist)
        if title and uuid:
            sub_parts.append(uuid)
        sub_text = "  •  ".join(sub_parts) if sub_parts else "no metadata"
        ctk.CTkLabel(
            info, text=sub_text, anchor="w", font=("Consolas", 10), text_color="#94a3b8",
        ).pack(anchor="w", fill="x")

        ctk.CTkButton(
            row, text="Restore", width=80, height=28,
            fg_color="#16a34a", hover_color="#15803d", font=("Inter", 11),
            command=lambda u=uuid: self._restore(u),
        ).grid(row=0, column=1, sticky="e", padx=(4, 10), pady=6)

    def _restore(self, uuid):
        if self.manifest is None:
            return
        self.manifest.untrash(uuid)
        self.refresh()
