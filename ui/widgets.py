import tkinter as tk
import customtkinter as ctk
from PIL import Image
from io import BytesIO
import os

def hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

class CollapsibleCard(ctk.CTkFrame):
    def __init__(self, parent, title, bg_color=None, corner_radius=6, padding=10, collapsed=True, **kwargs):
        super().__init__(parent, corner_radius=corner_radius, fg_color=bg_color, **kwargs)
        self.title = title
        self.collapsed = collapsed
        self.bg_color = bg_color
        self.padding = padding
        
        self.header_btn = ctk.CTkButton(
            self, 
            text=f"▶ {title}" if collapsed else f"▼ {title}", 
            command=self.toggle,
            fg_color="transparent", 
            hover_color=("gray75", "gray25"),
            anchor="w",
            font=("Segoe UI", 11, "bold"),
            height=30
        )
        self.header_btn.pack(fill="x", padx=5, pady=5)
        
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        
        if not collapsed:
            self.body.pack(fill="both", expand=True, padx=padding, pady=(0, padding))
            
    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.header_btn.configure(text=f"▶ {self.title}")
        else:
            self.body.pack(fill="both", expand=True, padx=self.padding, pady=(0, self.padding))
            self.header_btn.configure(text=f"▼ {self.title}")

    def set_summary(self, text):
        pass


class SongCard(ctk.CTkFrame):
    def __init__(self, parent, uuid, title, thumbnail_data=None, metadata=None, bg_color="transparent", show_checkbox=True, on_ignore=None, **kwargs):
        super().__init__(parent, fg_color=bg_color, **kwargs)
        self.uuid = uuid
        self.metadata = metadata or {}
        self.filepath = None
        self.on_ignore = on_ignore

        self.columnconfigure(2, weight=1)
        
        self.selected_var = ctk.BooleanVar(value=True)
        self.checkbox = None
        
        if show_checkbox:
            self.checkbox = ctk.CTkCheckBox(self, text="", variable=self.selected_var, width=24, height=24)
            self.checkbox.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=10)
        else:
             # Spacer to align if needed, or just nothing
             pass
        
        self.thumb_label = ctk.CTkLabel(self, text="♫", width=48, height=48, fg_color=("gray80", "gray20"))
        self.thumb_label.grid(row=0, column=1, rowspan=2, padx=5, pady=5)
        
        if thumbnail_data:
            self.set_thumbnail(thumbnail_data)
            
        display_title = title if len(title) < 40 else title[:37] + "..."
        self.title_label = ctk.CTkLabel(self, text=display_title, font=("Segoe UI", 14, "bold"), anchor="w")
        self.title_label.grid(row=0, column=2, sticky="ew", padx=5, pady=(5, 0))
        
        # Subtitle: tags · YYYY-MM-DD · short-uuid. The date + short UUID
        # disambiguate Suno's frequent same-title duplicates so users can tell
        # otherwise-identical preload rows apart.
        parts = []
        tags = self.metadata.get("tags") or ""
        if tags:
            parts.append(tags)
        created = self.metadata.get("created_at") or ""
        if created:
            parts.append(created[:10])
        if uuid:
            parts.append(uuid[:8])
        subtitle = " · ".join(parts) if parts else "Unknown"
        display_subtitle = subtitle if len(subtitle) <= 80 else subtitle[:77] + "..."
        self.subtitle_label = ctk.CTkLabel(self, text=display_subtitle, font=("Segoe UI", 12), text_color="gray", anchor="w")
        self.subtitle_label.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 5))
        
        self.status_label = ctk.CTkLabel(self, text="Waiting", font=("Segoe UI", 12))
        self.status_label.grid(row=0, column=3, padx=10, pady=5, sticky="e")
        
        self.progress_bar = ctk.CTkProgressBar(self, width=100)
        
        self.action_btn = ctk.CTkButton(self, text="▶", width=30, height=30, fg_color="transparent", command=self.on_action)

        if self.on_ignore is not None:
            self.ignore_btn = ctk.CTkButton(
                self, text="🚫", width=32, height=28,
                fg_color="transparent", hover_color="#7f1d1d",
                text_color="#9aa0a6", font=("Segoe UI", 12),
                command=self._handle_ignore,
            )
            self.ignore_btn.grid(row=0, column=5, rowspan=2, padx=(2, 8), pady=5)

    def _handle_ignore(self):
        if self.on_ignore is not None:
            self.on_ignore(self.uuid)

    def set_thumbnail(self, data):
        if not self.winfo_exists(): return
        try:
            image = Image.open(BytesIO(data))
            image = ctk.CTkImage(light_image=image, dark_image=image, size=(48, 48))
            self.thumb_label.configure(image=image, text="")
        except Exception:
            pass

    def set_status(self, status, progress=None):
        if not self.winfo_exists(): return
        self.status_label.configure(text=status)
        if status == "Downloading":
            self.status_label.configure(text_color=("blue", "#5c8bc4"))
            self.progress_bar.grid(row=1, column=3, padx=10, sticky="e")
            if progress is not None:
                self.progress_bar.set(progress / 100)
        elif status == "Complete":
            self.status_label.configure(text_color=("green", "#66bb6a"))
            self.progress_bar.grid_forget()
            self.action_btn.grid(row=0, column=4, rowspan=2, padx=5)
        elif status == "Error":
            self.status_label.configure(text_color=("red", "#f44336"))
            self.progress_bar.grid_forget()
        else:
            self.status_label.configure(text_color="gray")
            self.progress_bar.grid_forget()
            self.action_btn.grid_forget()

    def set_filepath(self, path):
        self.filepath = path

    def on_action(self):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(self.filepath)
            except: pass

    def is_selected(self):
        return self.selected_var.get()


class DownloadQueuePane(ctk.CTkScrollableFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.cards = {}
        
    def add_song(self, uuid, title, thumbnail_data=None, metadata=None):
        if uuid in self.cards: 
            return
        
        card = SongCard(self, uuid, title, thumbnail_data, metadata)
        card.pack(fill="x", pady=2, padx=5)
        self.cards[uuid] = card
        
    def update_song(self, uuid, status=None, progress=None, filepath=None):
        if uuid in self.cards:
            if status: self.cards[uuid].set_status(status, progress)
            if filepath: self.cards[uuid].set_filepath(filepath)

    def update_thumbnail(self, uuid, data):
        if uuid in self.cards:
            self.cards[uuid].set_thumbnail(data)
            
    def clear(self):
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()

    def get_selected_uuids(self):
        return [uuid for uuid, card in self.cards.items() if card.is_selected()]


class FilterPopup(ctk.CTkToplevel):
    def __init__(self, parent, current_filters, on_apply, active_workspace_name=None):
        super().__init__(parent)
        self.title("Filters")
        self.geometry("400x700")
        self.on_apply = on_apply
        self.current_filters = current_filters
        self.active_workspace_name = active_workspace_name or current_filters.get("workspace_name")
        self.clear_workspace_flag = False
        
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        
        ctk.CTkLabel(self, text="Filter Settings", font=("Segoe UI", 20, "bold")).pack(pady=15)
        
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # --- Section 1: Tags ---
        ctk.CTkLabel(scroll_frame, text="Tags", font=("Segoe UI", 14, "bold"), text_color="gray").pack(anchor="w", pady=(5,0))
        
        ctk.CTkLabel(scroll_frame, text="Include (comma separated)").pack(anchor="w")
        self.tags_include = ctk.CTkEntry(scroll_frame)
        self.tags_include.pack(fill="x", pady=5)
        if "tags_include" in current_filters:
            self.tags_include.insert(0, current_filters["tags_include"])
            
        ctk.CTkLabel(scroll_frame, text="Exclude").pack(anchor="w")
        self.tags_exclude = ctk.CTkEntry(scroll_frame)
        self.tags_exclude.pack(fill="x", pady=5)
        if "tags_exclude" in current_filters:
            self.tags_exclude.insert(0, current_filters["tags_exclude"])

        # --- Section 2: Active Workspace ---
        if self.active_workspace_name:
            ctk.CTkLabel(scroll_frame, text="Workspace", font=("Segoe UI", 14, "bold"), text_color="gray").pack(anchor="w", pady=(15,5))
            
            ws_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            ws_frame.pack(fill="x")
            
            self.ws_label = ctk.CTkLabel(ws_frame, text=f"📂 {self.active_workspace_name}", font=("Segoe UI", 12), text_color="#9aa0a6")
            self.ws_label.pack(side="left")
            
            ctk.CTkButton(ws_frame, text="Clear", width=60, height=24, fg_color="#f44336", hover_color="#b71c1c",
                          command=self._clear_workspace).pack(side="right")

        # --- Section 3: Status (Checkboxes) ---
        ctk.CTkLabel(scroll_frame, text="Status", font=("Segoe UI", 14, "bold"), text_color="gray").pack(anchor="w", pady=(15,0))
        
        status_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_columnconfigure(1, weight=1)
        
        self.vars = {}
        
        def add_cb(key, text, default, row, col):
            var = ctk.BooleanVar(value=current_filters.get(key, default))
            self.vars[key] = var
            ctk.CTkCheckBox(status_frame, text=text, variable=var).grid(row=row, column=col, sticky="w", pady=5, padx=5)

        add_cb("liked", "Liked Only", False, 0, 0)
        add_cb("hide_disliked", "Hide Disliked", True, 0, 1)
        add_cb("hide_gen_stems", "Hide Stems", True, 1, 0)
        add_cb("stems_only", "Stems Only", False, 1, 1)
        add_cb("hide_studio_clips", "Hide Clips", True, 2, 0)
        add_cb("is_public", "Public", False, 2, 1)
        add_cb("trashed", "Trash", False, 3, 0)

        # --- Section 4: Type (Radio) ---
        ctk.CTkLabel(scroll_frame, text="Type", font=("Segoe UI", 14, "bold"), text_color="gray").pack(anchor="w", pady=(15,0))
        
        self.type_var = ctk.StringVar(value=current_filters.get("type", "all"))
        
        type_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        type_frame.pack(fill="x", pady=5)
        
        ctk.CTkRadioButton(type_frame, text="All", variable=self.type_var, value="all").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(type_frame, text="Generations", variable=self.type_var, value="generations").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(type_frame, text="Uploads", variable=self.type_var, value="uploads").pack(anchor="w", pady=2)

        # Apply Button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(btn_frame, text="Apply Filters", command=self.apply, height=40).pack(fill="x")
        
    def _clear_workspace(self):
        self.clear_workspace_flag = True
        self.ws_label.configure(text="✓ Cleared", text_color="#66bb6a")

    def apply(self):
        filters = {
            "tags_include": self.tags_include.get(),
            "tags_exclude": self.tags_exclude.get(),
            "type": self.type_var.get()
        }
        
        # Add boolean vars
        for key, var in self.vars.items():
            filters[key] = var.get()
            
        if self.clear_workspace_flag:
            filters["clear_workspace"] = True
            
        self.on_apply(filters)
        self.destroy()


class WorkspaceBrowser(ctk.CTkToplevel):
    def __init__(self, parent, workspaces, on_select, bg_color="#1e1e1e", fg_color="#ffffff", accent_color="#5c8bc4", title="Select Workspace"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x500")
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.on_select = on_select
        
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 16, "bold")).pack(pady=10)
        
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for ws in workspaces:
            self._create_item(scroll_frame, ws)
            
    def _create_item(self, parent, ws):
        name = ws.get("name", "Untitled")
        # Check various keys for count
        count = ws.get('clip_count') or ws.get('num_tracks') or ws.get('total_clips') or ws.get('num_total_results') or ws.get('size') or 0
        date = ws.get('updated_at', '')[:10]
        
        card = ctk.CTkButton(parent, text=f"{name}\n{count} Songs • {date}", 
                             font=("Segoe UI", 12),
                             fg_color="transparent", border_width=1, border_color="#3a3a3d",
                             hover_color="#3a3a3d", anchor="w",
                             command=lambda: self._select(ws))
        card.pack(fill="x", pady=2)
        
    def _select(self, ws):
        self.on_select(ws)
        self.destroy()


class NeonProgressBar(ctk.CTkProgressBar):
    # Simple wrapper to match interface, or we just use normal progressbar
    def __init__(self, parent, height=10, colors=None, **kwargs):
        super().__init__(parent, height=height, **kwargs)
        self.configure(progress_color="#5c8bc4") # Purple
        
    def start(self, interval=20):
        self.configure(mode="indeterminate")
        self.start()
        
    def stop(self):
        self.stop()
        self.configure(mode="determinate")
        self.set(0)
        
    def set_text(self, text):
        pass # Not supported on native, maybe add label overlay later


class EmptyStateWidget(ctk.CTkFrame):
    def __init__(self, parent, theme, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(container, text="♪", font=("Segoe UI", 64), text_color="gray").pack(pady=(0, 16))
        ctk.CTkLabel(container, text="Ready to Sync", font=("Segoe UI", 14, "bold"), text_color="gray").pack()
        ctk.CTkLabel(container, text="Click 'Preload List' or 'Start Download' to begin", font=("Segoe UI", 10), text_color="gray").pack(pady=(8, 0))


class LibraryRow(ctk.CTkFrame):
    def __init__(self, parent, data, on_play=None, on_menu=None, odd_row=False, on_click=None, **kwargs):
        # Uniform background — no alternating stripes
        bg_color = "#252526"
        super().__init__(parent, fg_color=bg_color, corner_radius=0, height=35, **kwargs)
        self.data = data
        self.on_play = on_play
        self.on_menu = on_menu
        self.on_click_callback = on_click
        self.default_bg = bg_color
        self.selected_bg = "#5c8bc4"  # Purple accent (matching theme)
        self.is_selected = False
        self.hover_bg = "#2d2d30"


        # Configure grid columns to match header exactly
        self.grid_columnconfigure(0, weight=3, minsize=200) # Title
        self.grid_columnconfigure(1, weight=2, minsize=150) # Artist
        self.grid_columnconfigure(2, weight=2, minsize=150) # Genre
        self.grid_columnconfigure(3, weight=1, minsize=80)  # BPM
        self.grid_columnconfigure(4, weight=1, minsize=80)  # Duration
        
        # Import tooltip
        from ui.tooltip import ToolTip
        
        # 0. Artwork
        self.image_path = data.get("image_path")
        self.thumb_lbl = None
        if self.image_path and os.path.exists(self.image_path):
            try:
                from PIL import Image
                img = Image.open(self.image_path)
                # Resize to small square
                img = img.resize((30, 30), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
                self.thumb_lbl = ctk.CTkLabel(self, text="", image=ctk_img)
                self.thumb_lbl.grid(row=0, column=0, sticky="w", padx=(5, 5), pady=5)
            except:
                pass

        # 1. Title - Left aligned with truncation
        title = data.get("title", "Unknown")
        title_truncated = False
        if len(title) > 25:
            title_display = title[:22] + "..."
            title_truncated = True
        else:
            title_display = title

        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, sticky="ew", padx=(5, 5))
        
        if self.thumb_lbl:
            self.thumb_lbl.destroy()
            try:
                 from PIL import Image
                 img = Image.open(self.image_path)
                 img = img.resize((30, 30), Image.Resampling.LANCZOS)
                 ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
                 self.thumb_lbl = ctk.CTkLabel(self.title_frame, text="", image=ctk_img, width=30)
                 self.thumb_lbl.pack(side="left", padx=(0, 5))
            except: pass

        self.title_lbl = ctk.CTkLabel(self.title_frame, text=title_display, anchor="w",
                                      font=("Segoe UI", 11), text_color="#FFFFFF")
        self.title_lbl.pack(side="left", fill="x", expand=True)

        if title_truncated:
            ToolTip(self.title_lbl, title)
        
        # 2. Artist
        artist = data.get("artist", "Unknown")
        artist_truncated = False
        if len(artist) > 25:
            artist_display = artist[:22] + "..."
            artist_truncated = True
        else:
            artist_display = artist
        self.artist_lbl = ctk.CTkLabel(self, text=artist_display, anchor="w",
                                       font=("Segoe UI", 11), text_color="#9aa0a6")
        self.artist_lbl.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        if artist_truncated:
            ToolTip(self.artist_lbl, artist)
        
        # 3. Genre
        genre = data.get("genre", "--")
        genre_str = str(genre)
        genre_truncated = False
        if len(genre_str) > 20:
            genre_display = genre_str[:17] + "..."
            genre_truncated = True
        else:
            genre_display = genre_str
        self.genre_lbl = ctk.CTkLabel(self, text=genre_display, anchor="w",
                                      font=("Segoe UI", 11), text_color="#9aa0a6")
        self.genre_lbl.grid(row=0, column=2, sticky="ew", padx=5, pady=5)
        if genre_truncated:
            ToolTip(self.genre_lbl, genre_str)
        
        # 4. BPM
        bpm = data.get("bpm", "--")
        self.bpm_lbl = ctk.CTkLabel(self, text=str(bpm), anchor="center",
                                    font=("Segoe UI", 11), text_color="#9aa0a6")
        self.bpm_lbl.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        # 5. Duration
        dur_sec = data.get("duration", 0)
        mins, secs = divmod(dur_sec, 60)
        dur_str = f"{int(mins)}:{int(secs):02d}"
        self.dur_lbl = ctk.CTkLabel(self, text=dur_str, anchor="e",
                                    font=("Segoe UI", 11), text_color="#9aa0a6")
        self.dur_lbl.grid(row=0, column=4, sticky="ew", padx=(5, 10), pady=5)
        
        # Events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.bind("<Double-Button-1>", self.on_double_click)
        self.bind("<Button-3>", self.on_right_click)
        
        # Bind children to same events
        for child in self.winfo_children():
            child.bind("<Enter>", self.on_enter)
            child.bind("<Leave>", self.on_leave)
            child.bind("<Button-1>", self.on_click)
            child.bind("<Double-Button-1>", self.on_double_click)
            child.bind("<Button-3>", self.on_right_click)

    def set_selected(self, selected):
        self.is_selected = selected
        if self.winfo_exists():
            self.configure(fg_color=self.selected_bg if selected else self.default_bg)

    def on_enter(self, event):
        if not self.winfo_exists(): return
        if not self.is_selected:
            self.configure(fg_color=self.hover_bg)

    def on_leave(self, event):
        if not self.winfo_exists(): return
        if not self.is_selected:
            self.configure(fg_color=self.default_bg)

    def on_click(self, event):
        if not self.winfo_exists(): return
        if self.on_click_callback:
            self.on_click_callback(event, self.data, self)
            
    def on_double_click(self, event):
        if not self.winfo_exists(): return
        if self.on_play:
            self.on_play(self.data)

    def on_right_click(self, event):
        if not self.winfo_exists(): return
        if self.on_menu:
            self.on_menu(event, self.data)


class BubbleButton(ctk.CTkButton):
    """
    A unified 'Bubble' (Chip) component.
    Default: px-3 py-1 text-xs rounded-full bg-slate-800/50 text-slate-400
    Active: bg-violet-500/20 text-violet-300 border-violet-500/50
    """
    def __init__(self, parent, text, value, group_var=None, is_toggle=True, command=None, **kwargs):
        self.value = value
        self.group_var = group_var
        self.is_toggle = is_toggle
        self.user_command = command
        self._is_active = False

        # Theme Colors
        self.col_default = "#252526" # slate-800/50 approx
        self.col_hover = "#3a3a3d"   # slate-700
        self.col_active = "#3f6a9e"  # violet-900 (darker base for visibility) -> bg-violet-500/20
        self.col_active_bg = "#26333f" 
        
        self.text_default = "#9aa0a6" # slate-400
        self.text_active = "#82a9d6"  # violet-300
        
        self.border_default = "#3a3a3d" # slate-700/50
        self.border_active = "#5c8bc4"  # violet-500

        super().__init__(parent, text=text, 
                         height=24, # Smaller height
                         corner_radius=6,
                         border_width=1,
                         font=("Segoe UI", 11, "bold"), # Smaller font
                         fg_color=self.col_default,
                         text_color=self.text_default,
                         border_color=self.border_default,
                         hover_color=self.col_hover,
                         command=self._on_click,
                         **kwargs)
        
        # Initialize state based on variable
        if self.group_var:
            if self.is_toggle:
                # BooleanVar or similar
                try: 
                    self._is_active = bool(self.group_var.get())
                except: pass
            else:
                # StringVar for radio groups
                try:
                    self._is_active = (str(self.group_var.get()) == str(self.value))
                except: pass
        
        self._update_style()
        
        # Trace variable changes to update UI externally
        if self.group_var:
             self.group_var.trace_add("write", self._on_var_change)

    def _on_click(self):
        if self.is_toggle:
            self._is_active = not self._is_active
            if self.group_var:
                self.group_var.set(self._is_active)
        else:
            # Radio behavior: always set to active if clicked
            self._is_active = True
            if self.group_var:
                self.group_var.set(self.value)
        
        self._update_style()
        if self.user_command:
            self.user_command()

    def _on_var_change(self, *args):
        if not self.winfo_exists(): return
        # Update internal state from variable
        target_state = False
        if self.is_toggle:
            try: target_state = bool(self.group_var.get())
            except: pass
        else:
            try: target_state = (str(self.group_var.get()) == str(self.value))
            except: pass
            
        if self._is_active != target_state:
            self._is_active = target_state
            self._update_style()

    def _update_style(self):
        if self._is_active:
            self.configure(
                fg_color=self.col_active_bg,
                text_color=self.text_active,
                border_color=self.border_active
            )
        else:
            self.configure(
                fg_color=self.col_default,
                text_color=self.text_default,
                border_color=self.border_default
            )


class FlowLayout(ctk.CTkFrame):
    """
    A Frame that automatically wraps its children to new rows.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.bind("<Configure>", self._on_configure)
        self.children_list = []
        
    def add_widget(self, widget, padx=0, pady=0):
        self.children_list.append((widget, padx, pady))
        # Initial placement might be wrong until configure, but we can try
        pass

    def _on_configure(self, event=None):
        width = self.winfo_width()
        if width < 10: return
        
        x = 0
        y = 0
        line_height = 0
        
        for widget, padx, pady in self.children_list:
            
            w = widget.winfo_reqwidth() + (2 * padx)
            h = widget.winfo_reqheight() + (2 * pady)
            
            if x + w > width:
                x = 0
                y += line_height + 4 # row gap
                line_height = 0
            
            widget.place(x=x + padx, y=y + pady)
            x += w
            line_height = max(line_height, h)
            
        # Update own height
        required_height = y + line_height + 10
        self.configure(height=required_height)


class FilterBar(ctk.CTkFrame):
    def __init__(self, parent, filter_settings, on_change, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.settings = filter_settings
        self.on_change = on_change
        
        # Variables mapped to settings
        self.vars = {}
        self.show_advanced = False
        
        # --- Layout ---
        # 1. Tags Row (Split 50/50)
        # 2. Bubbles Primary (Flow)
        # 3. Bubbles Advanced (Flow, Hidden)
        
        # --- Tags Row ---
        tags_frame = ctk.CTkFrame(self, fg_color="transparent")
        tags_frame.pack(fill="x", pady=(0, 8))
        
        tags_frame.columnconfigure(0, weight=1)
        tags_frame.columnconfigure(1, weight=1)
        
        # Include
        self.vars["tags_include"] = ctk.StringVar(value=self.settings.get("tags_include", ""))
        self.vars["tags_include"].trace_add("write", self._notify_change)
        
        inc_frame = ctk.CTkFrame(tags_frame, fg_color="transparent")
        inc_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        ctk.CTkLabel(inc_frame, text="Include Tags", font=("Segoe UI", 11, "bold"), text_color="#c4c8cc").pack(anchor="w", pady=(0, 2))
        ti_entry = ctk.CTkEntry(inc_frame, textvariable=self.vars["tags_include"], 
                                placeholder_text="e.g. ambient, piano",
                                placeholder_text_color="gray50",
                                height=28, # Slimmer
                                fg_color="#1e1e1e", 
                                border_color="#252526",
                                text_color="#e0e0e0",
                                font=("Segoe UI", 11))
        ti_entry.pack(fill="x")
        
        # Exclude
        self.vars["tags_exclude"] = ctk.StringVar(value=self.settings.get("tags_exclude", ""))
        self.vars["tags_exclude"].trace_add("write", self._notify_change)
        
        exc_frame = ctk.CTkFrame(tags_frame, fg_color="transparent")
        exc_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        ctk.CTkLabel(exc_frame, text="Exclude Tags", font=("Segoe UI", 11, "bold"), text_color="#c4c8cc").pack(anchor="w", pady=(0, 2))
        te_entry = ctk.CTkEntry(exc_frame, textvariable=self.vars["tags_exclude"], 
                                placeholder_text="e.g. vocals, drums",
                                placeholder_text_color="gray50",
                                height=28, # Slimmer
                                fg_color="#1e1e1e", 
                                border_color="#252526",
                                text_color="#e0e0e0",
                                font=("Segoe UI", 11))
        te_entry.pack(fill="x")

        # --- Primary Bubbles ---
        self.primary_frame = FlowLayout(self)
        self.primary_frame.pack(fill="x", expand=True, pady=(0, 5))

        # --- Advanced Bubbles ---
        self.advanced_frame = FlowLayout(self)
        # Initially hidden (pack_forget is called in _toggle_advanced)
        
        def add_bubble(parent_frame, key, text, default_val=False):
            var = ctk.BooleanVar(value=self.settings.get(key, default_val))
            self.vars[key] = var
            var.trace_add("write", self._notify_change)
            btn = BubbleButton(parent_frame, text, None, group_var=var, is_toggle=True)
            parent_frame.add_widget(btn, padx=3, pady=3)

        type_var = ctk.StringVar(value=self.settings.get("type", "all"))
        self.vars["type"] = type_var
        type_var.trace_add("write", self._notify_change)

        def add_radio(parent_frame, text, val):
            btn = BubbleButton(parent_frame, text, val, group_var=type_var, is_toggle=False)
            parent_frame.add_widget(btn, padx=3, pady=3)

        # Primary Items
        add_radio(self.primary_frame, "All", "all")
        add_bubble(self.primary_frame, "liked", "Liked")
        add_radio(self.primary_frame, "Generations", "generations")
        add_radio(self.primary_frame, "Uploads", "uploads")
        add_bubble(self.primary_frame, "stems_only", "Stems Only")
        add_bubble(self.primary_frame, "hide_gen_stems", "Hide Stems", True)
        
        # Toggle Button (Advanced)
        self.adv_btn = BubbleButton(self.primary_frame, "⚙️ Advanced", None, is_toggle=False, command=self._toggle_advanced)
        self.primary_frame.add_widget(self.adv_btn, padx=3, pady=3)
        
        # Advanced Items
        add_bubble(self.advanced_frame, "disliked", "Disliked")
        add_bubble(self.advanced_frame, "is_public", "Public")
        add_bubble(self.advanced_frame, "is_private", "Private")
        add_bubble(self.advanced_frame, "trashed", "Trash")
        
        add_bubble(self.advanced_frame, "full_song", "Full Song")
        add_bubble(self.advanced_frame, "is_cover", "Cover")
        add_bubble(self.advanced_frame, "is_persona", "Persona")
        
        add_bubble(self.advanced_frame, "hide_disliked", "Hide Disliked", True)
        add_bubble(self.advanced_frame, "hide_studio_clips", "Hide Clips", True)
        
        # Initialize visibility state
        self._update_advanced_visibility()

    def _toggle_advanced(self):
        self.show_advanced = not self.show_advanced
        self._update_advanced_visibility()
        
    def _update_advanced_visibility(self):
        if self.show_advanced:
            self.advanced_frame.pack(fill="x", expand=True, pady=(5, 0))
            self.adv_btn.configure(text="▲ Advanced", text_color="#82a9d6", border_color="#5c8bc4")
        else:
            self.advanced_frame.pack_forget()
            self.adv_btn.configure(text="⚙️ Advanced", text_color="#9aa0a6", border_color="#3a3a3d")

    def _notify_change(self, *args):
        new_settings = {}
        for key, var in self.vars.items():
            new_settings[key] = var.get()
        self.on_change(new_settings)

    def set_filters(self, settings):
        for key, val in settings.items():
            if key in self.vars:
                try: self.vars[key].set(val)
                except: pass


class Dropdown(ctk.CTkToplevel):
    """
    An inline dropdown menu that floats over content.
    Supports loading, error, and list items.
    """
    def __init__(self, parent, on_select, width=200, height=300):
        super().__init__(parent)
        self.withdraw() # Hidden by default
        self.overrideredirect(True) # Borderless
        
        self.on_select = on_select
        self.width = width
        self.max_height = height
        
        # Style
        self.configure(fg_color="#1e1e1e") # bg-slate-900
        
        # Content Frame
        self.content_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", border_width=1, border_color="#3a3a3d")
        self.content_frame.pack(fill="both", expand=True)
        
        # Scrollable list
        self.scroll_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Loading/Error Overlay
        self.status_label = ctk.CTkLabel(self.content_frame, text="", font=("Segoe UI", 12), text_color="#9aa0a6")
        
        # Close on click outside (Binding to root is tricky, using focus out)
        self.bind("<FocusOut>", self._on_focus_out)
        
    def show(self, x, y, items=None):
        self.geometry(f"{self.width}x{self.max_height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        
        if items is not None:
            self.set_items(items)
            
    def hide(self):
        self.withdraw()
        
    def show_loading(self):
        self._clear_items()
        self.status_label.configure(text="⟳ Loading...", text_color="#c4c8cc")
        self.status_label.place(relx=0.5, rely=0.5, anchor="center")
        
    def show_error(self, message):
        self._clear_items()
        self.status_label.configure(text=f"⚠ {message}", text_color="#f44336")
        self.status_label.place(relx=0.5, rely=0.5, anchor="center")
        
    def show_empty(self, message="No items found"):
        self._clear_items()
        self.status_label.configure(text=message, text_color="#6a6a6e")
        self.status_label.place(relx=0.5, rely=0.5, anchor="center")

    def set_items(self, items):
        self.status_label.place_forget()
        self._clear_items()
        
        if not items:
            self.show_empty()
            return

        for item in items:
            self._add_item(item)
            
    def _add_item(self, item):
        # Item format: { "label": str, "value": any, "sublabel": str (optional) }
        label = item.get("label", "Unknown")
        sublabel = item.get("sublabel", "")
        
        # Container for hover effect
        btn = ctk.CTkButton(self.scroll_frame, text=label, anchor="w",
                            font=("Segoe UI", 12),
                            fg_color="transparent", 
                            text_color="#e0e0e0",
                            hover_color="#3f6a9e", # violet-900/50
                            height=32,
                            command=lambda: self._on_item_click(item))
        btn.pack(fill="x", pady=0)
        
        # TODO: Add sublabel support if needed (requires custom frame instead of button)

    def _on_item_click(self, item):
        self.on_select(item)
        self.hide()

    def _clear_items(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

    def _on_focus_out(self, event):
        # Delay hiding to allow click events to register
        self.after(100, self.hide)


