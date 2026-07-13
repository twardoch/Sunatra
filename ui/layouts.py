"""Layout builders and dialog helpers for SunoSync GUI."""
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import webbrowser
import pyperclip
from ui.widgets import CollapsibleCard, FilterPopup, WorkspaceBrowser

# Note: App instance passed here is expected to be a CTk class (from main.py)

def create_auth_card(parent, app):
    """Create the authorization card with token input."""
    # Parent is likely a scrollable frame or main frame
    bg = getattr(app, 'card_bg', '#2d2d30')
    card = CollapsibleCard(parent, title="Authorization", bg_color=bg,
                          corner_radius=6, padding=12, collapsed=False)
    card.pack(fill="x", pady=(0, 12))
    
    body = card.body
    
    ctk.CTkLabel(body, text="Bearer Token", font=("Segoe UI", 12, "bold"), text_color="gray").pack(anchor="w", padx=5, pady=(5, 0))
    
    # Input Row
    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(fill="x", padx=5, pady=5)
    
    app.token_var = ctk.StringVar()
    app.token_entry = ctk.CTkEntry(row, textvariable=app.token_var, show="●", width=300)
    app.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    get_token_btn = ctk.CTkButton(row, text="Get Token", command=app.get_token_logic, width=100)
    get_token_btn.pack(side="right")
    
    return card


def create_settings_card(parent, app, base_path):
    """Create the settings card with path and toggles."""
    bg = getattr(app, 'card_bg', '#2d2d30')
    card = CollapsibleCard(parent, title="Download Settings", bg_color=bg,
                          corner_radius=6, padding=12, collapsed=False)
    card.pack(fill="x", pady=(0, 12))
    body = card.body
    
    # --- Downloads Path ---
    ctk.CTkLabel(body, text="Downloads Folder", font=("Segoe UI", 12, "bold"), text_color="gray").pack(anchor="w", padx=5, pady=(5, 0))
    ctk.CTkLabel(body, text="Where new downloads land.", font=("Segoe UI", 10), text_color="#6a6a6e").pack(anchor="w", padx=5)

    path_row = ctk.CTkFrame(body, fg_color="transparent")
    path_row.pack(fill="x", padx=5, pady=5)

    app.path_var = ctk.StringVar(value=os.path.join(base_path, "Suno_Downloads"))
    app.path_display_var = ctk.StringVar()

    path_entry = ctk.CTkEntry(path_row, textvariable=app.path_display_var, state="readonly")
    path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    browse_btn = ctk.CTkButton(path_row, text="Browse", command=app.browse_folder, width=80)
    browse_btn.pack(side="right")

    # --- Library Path ---
    ctk.CTkLabel(body, text="Library Folder", font=("Segoe UI", 12, "bold"), text_color="gray").pack(anchor="w", padx=5, pady=(10, 0))
    ctk.CTkLabel(body, text="Where curated keepers live (use \u201cAdd to Library\u201d in the Downloads tab).", font=("Segoe UI", 10), text_color="#6a6a6e").pack(anchor="w", padx=5)

    library_row = ctk.CTkFrame(body, fg_color="transparent")
    library_row.pack(fill="x", padx=5, pady=5)

    app.library_path_var = ctk.StringVar(value=os.path.join(base_path, "Suno_Library"))
    app.library_path_display_var = ctk.StringVar()

    library_entry = ctk.CTkEntry(library_row, textvariable=app.library_path_display_var, state="readonly")
    library_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    library_browse_btn = ctk.CTkButton(library_row, text="Browse", command=app.browse_library_folder, width=80)
    library_browse_btn.pack(side="right")

    # --- Toggles Grid ---
    toggles_frame = ctk.CTkFrame(body, fg_color="transparent")
    toggles_frame.pack(fill="x", padx=5, pady=10)
    
    toggles_frame.columnconfigure(0, weight=1)
    toggles_frame.columnconfigure(1, weight=1)
    
    # Helpers
    def add_toggle(row, col, text, var, tooltip=""):
        # Wrapper frame not strictly needed for alignment in grid but good for consistency
        s = ctk.CTkSwitch(toggles_frame, text=text, variable=var)
        s.grid(row=row, column=col, sticky="w", padx=10, pady=8)
        # Tooltip logic removed for now or needs a CTkTooltip lib.

    app.embed_thumb_var = ctk.BooleanVar(value=True)
    add_toggle(0, 0, "Embed Metadata", app.embed_thumb_var)
    
    app.download_wav_var = ctk.BooleanVar(value=False)
    add_toggle(0, 1, "Prefer WAV", app.download_wav_var)
    
    app.organize_var = ctk.BooleanVar(value=False)
    add_toggle(1, 0, "Monthly Folders", app.organize_var)
    
    app.save_lyrics_var = ctk.BooleanVar(value=True)
    add_toggle(1, 1, "Save Lyrics (.txt)", app.save_lyrics_var)

    app.track_folder_var = ctk.BooleanVar(value=False)
    add_toggle(2, 0, "Stem Track Folder", app.track_folder_var)

    app.playlist_folder_var = ctk.BooleanVar(value=False)
    add_toggle(2, 1, "Playlist/Workspace Folders", app.playlist_folder_var)

    app.smart_resume_var = ctk.BooleanVar(value=False)
    add_toggle(3, 1, "Smart Resume", app.smart_resume_var)
    
    app.disable_sounds_var = ctk.BooleanVar(value=False)
    add_toggle(3, 0, "Disable Notification Sounds", app.disable_sounds_var)
    
    return card


def create_scraping_card(parent, app):
    """Create the scraping options card."""
    bg = getattr(app, 'card_bg', '#2d2d30')
    card = CollapsibleCard(parent, title="Scraping Options", bg_color=bg,
                          corner_radius=6, padding=12, collapsed=False)
    card.pack(fill="x", pady=(0, 12))
    body = card.body
    
    # Horizontal layout for inputs
    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(fill="x", padx=5, pady=10)
    
    def add_input(frame, label, var, width=60):
        c = ctk.CTkFrame(frame, fg_color="transparent")
        c.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(c, text=label, font=("Segoe UI", 12, "bold"), text_color="gray").pack(anchor="w")
        # Spinbox doesn't exist natively in basic CTk, using Entry for now or external lib. 
        # Actually CTk doesn't have Spinbox. We'll use Entry with validation ideally, or just Entry.
        # User can type number.
        e = ctk.CTkEntry(c, textvariable=var, width=width)
        e.pack()
        return e

    app.rate_limit_var = ctk.DoubleVar(value=0.5) # Using DoubleVar for entry works if careful
    add_input(row, "Delay (s)", app.rate_limit_var)
    
    app.start_page_var = ctk.IntVar(value=1)
    add_input(row, "Start Page", app.start_page_var)
    
    app.max_pages_var = ctk.IntVar(value=0)
    add_input(row, "Max Pages", app.max_pages_var)

    # Filter/Workspace Buttons Frame
    filter_frame = ctk.CTkFrame(body, fg_color="transparent")
    filter_frame.pack(fill="x", padx=5, pady=(0, 10))
    
    app.filter_btn = ctk.CTkButton(filter_frame, text="Filters", command=app.open_filters, fg_color="transparent", border_width=1)
    app.filter_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
    
    app.workspace_btn = ctk.CTkButton(filter_frame, text="Workspaces", command=app.open_workspaces, fg_color="transparent", border_width=1)
    app.workspace_btn.pack(side="left", fill="x", expand=True, padx=5)

    app.playlist_btn = ctk.CTkButton(filter_frame, text="Playlists", command=app.open_playlists, fg_color="transparent", border_width=1)
    app.playlist_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

    # Preload Button
    app.preload_btn = ctk.CTkButton(body, text="Preload List", command=app.preload_songs, fg_color="#3f6a9e", hover_color="#3f6a9e")
    app.preload_btn.pack(fill="x", padx=5, pady=(5, 0))
    
    app.force_rescan_var = ctk.BooleanVar(value=False)
    rescan_chk = ctk.CTkCheckBox(body, text="Force Rescan (Ignore Cache)", variable=app.force_rescan_var, font=("Segoe UI", 11), text_color="gray")
    rescan_chk.pack(anchor="e", padx=10, pady=(5, 5))

    return card


def create_action_area(parent, app):
    """Create the action buttons area."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", pady=10)
    
    # Start Button (Primary)
    app.start_btn = ctk.CTkButton(frame, text="Start Download", command=app.start_download_thread,
                                  height=45, font=("Segoe UI", 16, "bold"), fg_color="#3f6a9e", hover_color="#3f6a9e")
    app.start_btn.pack(side="left", padx=(0, 10), fill="x", expand=True)
    
    # Stop Button (Destructive)
    app.stop_btn = ctk.CTkButton(frame, text="Stop", command=app.stop_download,
                                height=45, font=("Segoe UI", 16, "bold"), fg_color="transparent", 
                                border_color="#f44336", border_width=2, text_color="#f44336", hover_color="#450a0a")
    app.stop_btn.pack(side="left", padx=(0, 0))
    app.stop_btn.configure(state="disabled")
    
    return frame


def create_token_dialog(app):
    """Create and show the token acquisition dialog."""
    try:
        app.log("Opening Suno in your default browser...", "info")
        webbrowser.open("https://suno.com")
    except Exception:
        pass
    
    try:
        dialog = ctk.CTkToplevel(app)
        dialog.title("Get Token")
        dialog.geometry("620x600")
        dialog.attributes("-topmost", True)
        dialog.lift()
        dialog.focus_force()
    except Exception:
        return

    ctk.CTkLabel(dialog, text="CONNECT TO SUNO", font=("Segoe UI", 18, "bold")).pack(pady=15)

    # --- Option 1: Chrome Extension (Recommended) ---
    ext_frame = ctk.CTkFrame(dialog, fg_color="#252526", corner_radius=6)
    ext_frame.pack(fill="x", padx=20, pady=(0, 10))

    ctk.CTkLabel(ext_frame, text="⚡ Option 1 — Chrome Extension (Recommended)",
                 font=("Segoe UI", 13, "bold"), text_color="#66bb6a").pack(anchor="w", padx=12, pady=(10, 5))

    ext_steps = (
        "1. Open Chrome → navigate to chrome://extensions\n"
        "2. Enable 'Developer mode' (top-right toggle)\n"
        "3. Click 'Load unpacked' → select the chrome_extension folder\n"
        "4. Log in to suno.com — token syncs automatically!"
    )
    ctk.CTkLabel(ext_frame, text=ext_steps, justify="left", font=("Segoe UI", 11),
                 text_color="#9aa0a6").pack(anchor="w", padx=12, pady=(0, 10))

    # --- Divider ---
    ctk.CTkLabel(dialog, text="— OR —", font=("Segoe UI", 11), text_color="#6a6a6e").pack(pady=5)

    # --- Option 2: Manual (Original) ---
    manual_frame = ctk.CTkFrame(dialog, fg_color="#252526", corner_radius=6)
    manual_frame.pack(fill="x", padx=20, pady=(0, 10))

    ctk.CTkLabel(manual_frame, text="📋 Option 2 — Manual (Console)",
                 font=("Segoe UI", 13, "bold"), text_color="#5c8bc4").pack(anchor="w", padx=12, pady=(10, 5))

    steps = (
        "1. Log in to Suno in the opened browser tab.\n"
        "2. Press F12 to open Developer Tools.\n"
        "3. Go to the 'Console' tab.\n"
        "4. Copy the code below and paste it, then press Enter."
    )
    ctk.CTkLabel(manual_frame, text=steps, justify="left", font=("Segoe UI", 11),
                 text_color="#9aa0a6").pack(anchor="w", padx=12, pady=(0, 5))
    
    code = "window.Clerk.session.getToken().then(t => prompt('Copy this token:', t))"
    
    code_frame = ctk.CTkFrame(manual_frame, fg_color="#2d2d30")
    code_frame.pack(fill="x", padx=12, pady=5)
    
    code_entry = ctk.CTkEntry(code_frame, font=("Consolas", 11))
    code_entry.insert(0, code)
    code_entry.configure(state="readonly")
    code_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
    
    def copy_code():
        pyperclip.copy(code)
        
    ctk.CTkButton(code_frame, text="Copy", command=copy_code, width=50, height=24,
                  fg_color="#3a3a3d", hover_color="#5a5a5f").pack(side="left", padx=8)
    copy_code() # Auto copy
    
    ctk.CTkLabel(manual_frame, text="5. Copy the token from the popup → paste below:",
                 justify="left", font=("Segoe UI", 11), text_color="#9aa0a6").pack(anchor="w", padx=12, pady=(5, 2))
    
    token_input = ctk.CTkEntry(manual_frame, fg_color="#2d2d30", border_color="#3a3a3d",
                               text_color="#fff", font=("Segoe UI", 11))
    token_input.pack(fill="x", padx=12, pady=(0, 10))
    token_input.focus_set()
    
    def submit():
        t = token_input.get().strip()
        if t:
            app.token_var.set(t)
            app.log("Token set successfully!", "success")
            app.save_config()
            dialog.destroy()
        else:
            pass
    
    ctk.CTkButton(dialog, text="Submit Token", command=submit, height=40,
                  fg_color="#3f6a9e", hover_color="#3f6a9e").pack(pady=15)
