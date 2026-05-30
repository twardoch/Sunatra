import datetime
import os
import shutil

import customtkinter as ctk

from sunatra.ui.layouts import create_settings_card
from sunatra.ui.widgets import CollapsibleCard


class SettingsTab(ctk.CTkFrame):
    """
    Global Application Settings View.
    """
    def __init__(self, parent, config_manager, manifest=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.config_manager = config_manager
        self.manifest = manifest
        self.card_bg = "#27272a"

        # UI Setup
        self._setup_layout()
        self.load_settings()

    def _setup_layout(self):
        # Title
        title = ctk.CTkLabel(self, text="Settings", font=("Inter", 24, "bold"))
        title.pack(anchor="w", padx=20, pady=(20, 10))

        # Scrollable container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # Use Layout Helper for common settings
        # We need to simulate 'app' object interface expected by create_settings_card
        # So we initialize the variables it expects
        self.init_variables()

        base_path = os.getcwd()
        self.settings_card = create_settings_card(self.container, self, base_path)

        # Add a Save Button/Indicator?
        # create_settings_card binds vars to nothing (it just uses them).
        # We need to bind them to save_config.



        self.app_card = CollapsibleCard(self.container, title="Application", collapsed=False)
        self.app_card.pack(fill="x", pady=10)

        self.disable_sounds_var = ctk.BooleanVar(value=False)
        s = ctk.CTkSwitch(self.app_card.body, text="Disable Notification Sounds", variable=self.disable_sounds_var)
        s.pack(anchor="w", padx=10, pady=10)

        # --- Scan Settings ---
        self.scan_card = CollapsibleCard(self.container, title="Scan Configuration", collapsed=False)
        self.scan_card.pack(fill="x", pady=10)

        # Grid layout for scan settings
        scan_inner = ctk.CTkFrame(self.scan_card.body, fg_color="transparent")
        scan_inner.pack(fill="x", padx=10, pady=5)

        def add_scan_row(row, label, var, hint):
            ctk.CTkLabel(scan_inner, text=label, width=120, anchor="w").grid(row=row, column=0, pady=5, sticky="w")
            ctk.CTkEntry(scan_inner, textvariable=var, width=80).grid(row=row, column=1, pady=5, sticky="w", padx=10)
            ctk.CTkLabel(scan_inner, text=hint, text_color="gray", font=("Inter", 11)).grid(row=row, column=2, pady=5, sticky="w")

        add_scan_row(0, "Speed (Delay):", self.scan_speed_var, "Seconds between API requests (0.5s default)")
        add_scan_row(1, "Start Page:", self.scan_start_var, "Library page to start scanning from")
        add_scan_row(2, "Max Pages:", self.scan_max_var, "Limit number of pages to scan (0 = Unlimited)")

        # Trashed Songs UI lives in its own "Ignored" sidebar tab now.

        # --- Maintenance & Debugging ---
        self.maint_card = CollapsibleCard(self.container, title="Maintenance & Debugging", collapsed=False)
        self.maint_card.pack(fill="x", pady=10)

        # 1. Force Rescan
        self.force_rescan_var = ctk.BooleanVar(value=False)
        rescan_frame = ctk.CTkFrame(self.maint_card.body, fg_color="transparent")
        rescan_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkCheckBox(rescan_frame, text="Force Rescan", variable=self.force_rescan_var).pack(anchor="w")
        ctk.CTkLabel(rescan_frame, text="Forces the downloader to re-check the server for every file, even if it exists locally.\nUseful if downloads were interrupted or files are corrupted.",
                     text_color="gray", font=("Inter", 11), justify="left").pack(anchor="w", padx=28)

        # 2. Clear Cache
        cache_frame = ctk.CTkFrame(self.maint_card.body, fg_color="transparent")
        cache_frame.pack(fill="x", padx=5, pady=10)

        ctk.CTkButton(cache_frame, text="🧹 Sweep Cache", width=120, fg_color="#333", hover_color="#444",
                      command=self.clear_cache).pack(anchor="w", padx=5)
        ctk.CTkLabel(cache_frame, text="Clears the internal list of 'seen' songs for the current session.\nDoes not delete files. Resets the queue so you can add songs again.",
                     text_color="gray", font=("Inter", 11), justify="left").pack(anchor="w", padx=5, pady=(2,0))

        # 3. Debug Log
        debug_frame = ctk.CTkFrame(self.maint_card.body, fg_color="transparent")
        debug_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(debug_frame, text="🐞 Open Debug Log", width=120, fg_color="#333", hover_color="#444",
                      command=self.open_debug).pack(anchor="w", padx=5)
        ctk.CTkLabel(debug_frame, text="View raw internal logs and API responses.\nUseful for troubleshooting errors or reporting bugs.",
                     text_color="gray", font=("Inter", 11), justify="left").pack(anchor="w", padx=5, pady=(2,0))

        ctk.CTkButton(debug_frame, text="📤 Export Log File", width=120, fg_color="#333", hover_color="#444",
                      command=self.export_log).pack(anchor="w", padx=5, pady=(10, 0))
        ctk.CTkLabel(debug_frame, text="Save the 'debug.log' file to share with developer.",
                     text_color="gray", font=("Inter", 11), justify="left").pack(anchor="w", padx=5, pady=(2,0))

        self.save_btn = ctk.CTkButton(self, text="Save Settings", command=self.save_settings, width=200)
        self.save_btn.pack(pady=20)

    def init_variables(self):
        # Variables expected by create_settings_card
        self.path_var = ctk.StringVar()
        self.path_display_var = ctk.StringVar()

        self.embed_thumb_var = ctk.BooleanVar(value=True)
        self.download_wav_var = ctk.BooleanVar(value=False)
        self.organize_var = ctk.BooleanVar(value=False)
        self.save_lyrics_var = ctk.BooleanVar(value=True)
        self.track_folder_var = ctk.BooleanVar(value=False)
        self.playlist_folder_var = ctk.BooleanVar(value=False)
        self.smart_resume_var = ctk.BooleanVar(value=False)

        # Scan vars
        self.scan_speed_var = ctk.DoubleVar(value=0.5)
        self.scan_start_var = ctk.IntVar(value=1)
        self.scan_max_var = ctk.IntVar(value=0)

        # Dummy variables for "app" interface if needed by other components,
        # but create_settings_card only uses the above.

    def browse_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(initialdir=self.path_var.get(), title="Select Downloads Folder")
        if path:
            self.path_var.set(path)
            self.path_display_var.set(path)

    def browse_library_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(initialdir=self.library_path_var.get(), title="Select Library Folder")
        if path:
            self.library_path_var.set(path)
            self.library_path_display_var.set(path)

    def clear_cache(self):
        # Access DownloaderTab logic
        if hasattr(self.master.master, 'views') and "downloader" in self.master.master.views:
             # self.master.master is likely the Content Area, so we need to go up to SunatraApp?
             # Actually parent passed to __init__ is self.content_area.
             # self.master is content_area. self.master.master is SunatraApp.
             # Ideally we shouldn't rely on strict hierarchy, but let's try safely.
             try:
                 app = self.winfo_toplevel()
                 if hasattr(app, 'views') and "downloader" in app.views:
                     app.views["downloader"].clear_uuid_cache()
             except Exception as e:
                 print(f"Error accessing downloader: {e}")

    def open_debug(self):
         try:
             app = self.winfo_toplevel()
             if hasattr(app, 'views') and "downloader" in app.views:
                 app.views["downloader"].open_debug_window()
         except Exception as e:
             print(f"Error accessing debug: {e}")

    def export_log(self):
        from tkinter import filedialog, messagebox

        # Check if debug.log exists
        log_file = "debug.log"
        if not os.path.exists(log_file):
            messagebox.showerror("Error", "No debug log found (debug.log missing).")
            return

        # timestamp for filename
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"Sunatra_Log_{ts}.txt"

        target = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=default_name,
            title="Export Debug Log"
        )

        if target:
            try:
                shutil.copy(log_file, target)
                messagebox.showinfo("Success", f"Log exported to:\n{target}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export log: {e}")

    def load_settings(self):
        c = self.config_manager
        downloads = c.get("downloads_path") or c.get("path", "")
        library = c.get("library_path") or c.get("path", "")
        self.path_var.set(downloads)
        self.path_display_var.set(downloads)
        self.library_path_var.set(library)
        self.library_path_display_var.set(library)

        self.embed_thumb_var.set(c.get("embed_metadata", True))
        self.download_wav_var.set(c.get("prefer_wav", False))
        self.organize_var.set(c.get("organize", False))
        self.save_lyrics_var.set(c.get("save_lyrics", True))
        self.track_folder_var.set(c.get("track_folder", False))
        self.playlist_folder_var.set(c.get("playlist_folder", False))
        self.smart_resume_var.set(c.get("smart_resume", False))
        self.disable_sounds_var.set(c.get("disable_sounds", False))
        self.force_rescan_var.set(c.get("force_rescan", False))

        self.scan_speed_var.set(c.get("download_delay", 0.5))
        self.scan_start_var.set(c.get("start_page", 1))
        self.scan_max_var.set(c.get("max_pages", 0))

    def save_settings(self):
        c = self.config_manager
        c.set("downloads_path", self.path_var.get())
        c.set("library_path", self.library_path_var.get())
        c.set("embed_metadata", self.embed_thumb_var.get())
        c.set("prefer_wav", self.download_wav_var.get())
        c.set("organize", self.organize_var.get())
        c.set("save_lyrics", self.save_lyrics_var.get())
        c.set("track_folder", self.track_folder_var.get())
        c.set("playlist_folder", self.playlist_folder_var.get())
        c.set("smart_resume", self.smart_resume_var.get())
        c.set("disable_sounds", self.disable_sounds_var.get())
        c.set("force_rescan", self.force_rescan_var.get())

        c.set("download_delay", self.scan_speed_var.get())
        c.set("start_page", self.scan_start_var.get())
        c.set("max_pages", self.scan_max_var.get())
        c.save_config()

        # Show toast
        from tkinter import messagebox
        messagebox.showinfo("Saved", "Settings saved successfully.")
