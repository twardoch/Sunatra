import os
import sys
import threading
import json
import ctypes
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

import logging

# --- Logging Setup ---
LOG_FILE = "debug.log"
handlers = [logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers
)

# Redirect stdout/stderr to logging
class StreamToLogger(object):
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())
    
    def flush(self):
        pass

sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)

logging.info("Logging initialized. Starting application...")

# FIX: Prevent crash in frozen noconsole mode where sys.stdout/stderr are None
# This typically affects http.server which tries to log to stderr
if getattr(sys, 'frozen', False):
    # If frozen, we've already redirected to logger, so we might not need NulLWriter check
    # But just in case logging setup failed or something resets it:
    pass

from ui.widgets import WorkspaceBrowser
from core.config_manager import ConfigManager
from core.downloader import SunoDownloader
from core.manifest import LibraryManifest, LOCATION_LIBRARY
from core.version import __version__ as APP_VERSION
from ui.sidebar import Sidebar
from ui.library import LibraryTab
from ui.downloader_tab import DownloaderTab
from ui.settings import SettingsTab
from ui.player import PlayerWidget
from core.theme import ThemeManager

from services.media_keys import MediaKeyHandler
from services.bug_reporter import show_crash_popup
from services.token_server import TokenServer

import sentry_sdk

# Initialize Sentry
# NOTE: User must replace 'YOUR_DSN_HERE' with their actual DSN
SENTRY_DSN = "YOUR_DSN_HERE"

if SENTRY_DSN and SENTRY_DSN != "YOUR_DSN_HERE":
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
    except Exception as e:
        print(f"Sentry init failed: {e}")
else:
    print("Sentry not initialized (Placeholder DSN detected).")

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to Log to Sentry and show UI popup."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    print("Uncaught exception:", exc_value)
    
    # Send to Sentry
    sentry_sdk.capture_exception(exc_value)
    
    # Show Popup (Ensure it runs on main thread if possible, though here we might be in a crash state)
    # We just call it directly as a blocking call before exit.
    show_crash_popup(exc_value)

sys.excepthook = handle_exception

# --- Constants ---
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = "config.json"
CACHE_FILE = os.path.join(base_path, "library_cache.json")
TAGS_FILE = os.path.join(base_path, "tags.json")
CHANGELOG_FILE = os.path.join(base_path, "changelog.txt")

# Set CTk Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

from services.updater import Updater
import webbrowser

class SunoSyncApp(ctk.CTk):
    """Main application with Downloader, Library, and Player."""
    
    def __init__(self):
        super().__init__()
        
        # Window Setup
        self.title("SunoSync")
        
        # 1. Set AppUserModelID (Separates icon in Taskbar)
        try:
            myappid = 'sunosync.app.v2' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # 2. Load Icons
        try:
            # Window Icon (Titlebar)
            logo_icon_path = resource_path("assets/SunoSyncLogoIcon.png")
            if os.path.exists(logo_icon_path):
                # Use PIL for better PNG support
                pil_logo = Image.open(logo_icon_path)
                self.logo_img = ImageTk.PhotoImage(pil_logo)
                self.wm_iconphoto(False, self.logo_img) 

            # Taskbar Icon
            taskbar_icon_path = resource_path("assets/TaskbarDesktopIcon.png")
            if os.path.exists(taskbar_icon_path):
                pil_taskbar = Image.open(taskbar_icon_path)
                self.taskbar_img = ImageTk.PhotoImage(pil_taskbar)
                self.wm_iconphoto(True, self.taskbar_img)
        except Exception as e:
            print(f"Icon error: {e}")

        # 3. Center Window Logic
        width = 1100
        height = 750
        self.minsize(1000, 750)
        
        # Calculate Center
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int((screen_width - width) / 2)
        center_y = int((screen_height - height) / 2)
        
        default_geo = f"{width}x{height}+{center_x}+{center_y}"
        self.geometry(default_geo)

        self.config_manager = ConfigManager(CONFIG_FILE)
        self.manifest = LibraryManifest()
        self._run_path_migration()

        # Initialize Managers and Theme
        self.theme = ThemeManager() # Kept passing for tabs that still use it
        self.theme.apply_treeview_style()
        self.configure(fg_color=self.theme.bg_dark)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # State
        self.current_view = None
        self.views = {}
        
        self.load_window_state()
        self._setup_ui()
        
        # Show splash
        self.after(100, self.show_splash)
        


        # Check for updates
        Updater.check_for_updates(self.show_update_bar)

        # Start Token Server (for Chrome Extension)
        self.token_server = TokenServer()
        self.token_server.on_token(self._on_extension_token)
        self.token_server.start()

    def show_update_bar(self, version, url):
        """Display the update bar at the top of the app."""
        # Use .after to ensure UI updates happen on main thread
        self.after(0, lambda: self._create_update_bar(version, url))

    def _create_update_bar(self, version, url):
        self.update_bar = ctk.CTkFrame(self, fg_color="#66bb6a", height=30, corner_radius=0)
        
        # Unmap existing to shift them down
        self.sidebar.grid_forget()
        self.content_area.grid_forget()
        if hasattr(self, 'lyrics_panel'): self.lyrics_panel.grid_forget()
        self.player.grid_forget()
        
        # Configure New Row 0 for Update Bar
        self.update_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        
        lbl = ctk.CTkLabel(self.update_bar, text=f"✨ New version v{version} available!", text_color="white", font=("Segoe UI", 12, "bold"))
        lbl.pack(side="left", padx=20, pady=2)
        
        # Close Button (Rightmost)
        close_btn = ctk.CTkButton(self.update_bar, text="✕", width=30, height=20, fg_color="transparent", 
                                  text_color="white", hover_color="#43a047", command=self._close_update_bar)
        close_btn.pack(side="right", padx=(5, 20), pady=2)

        btn = ctk.CTkButton(self.update_bar, text="Download", width=80, height=20, fg_color="white", text_color="#66bb6a", 
                            hover_color="#f0fdf4", command=lambda: webbrowser.open(url))
        btn.pack(side="right", padx=5, pady=2)
        
        # Re-grid others at +1 Row
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.content_area.grid(row=1, column=1, sticky="nsew", padx=20, pady=20)
        if hasattr(self, 'lyrics_panel') and self.lyrics_panel.is_visible:
             self.lyrics_panel.grid(row=1, column=2, rowspan=2, sticky="ns")
        
        self.player.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        self.grid_rowconfigure(0, weight=0) # Bar fixed
        self.grid_rowconfigure(1, weight=1) # Main content expands
        self.grid_rowconfigure(2, weight=0) # Player fixed

    def _close_update_bar(self):
        """Close the update bar and restore layout."""
        if hasattr(self, 'update_bar'):
            self.update_bar.destroy()
            del self.update_bar
            
        # Unmap logic to prevent visual glitches during shift
        self.sidebar.grid_forget()
        self.content_area.grid_forget()
        if hasattr(self, 'lyrics_panel'): self.lyrics_panel.grid_forget()
        self.player.grid_forget()
        
        # Restore Original Layout (Row 0 Content, Row 1 Player)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        if hasattr(self, 'lyrics_panel') and self.lyrics_panel.is_visible:
             self.lyrics_panel.grid(row=0, column=2, rowspan=2, sticky="ns")
        
        self.player.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        # Reset Grid Weights
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0) # Clear weight for row 2

    def _setup_ui(self):

        """Configure the main layout."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar (Left)
        # Note: Sidebar is now a CTkFrame
        self.sidebar = Sidebar(self, self.show_view)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Content Area (Right)
        # We use a container frame for content
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Initialize Views
        # IMPORTANT: These classes (DownloaderTab, LibraryTab, etc.) need to be instantiated.
        # Currently they are still Tkinter classes. Mixing CTk parent with Tk child works but
        # we aim to migrate them. For now, we pass 'self.content_area' which is a CTkFrame.
        
        try:
            self.downloader = DownloaderTab(self.content_area, config_manager=self.config_manager, manifest=self.manifest)
            self.views["downloader"] = self.downloader
            
            # For Library, we need the Player widget instance first?
            # Creating Player Widget first (to pass to library)
            # Player is at the bottom? The original had it at bottom.
            # Updated layout: Persistent player bar at bottom row.
            
            self.player = PlayerWidget(self, bg_color=self.theme.player_bg)
            self.player.grid(row=1, column=0, columnspan=2, sticky="ew")
            self.player.set_tags_file(TAGS_FILE)

            self.library = LibraryTab(self.content_area, config_manager=self.config_manager, cache_file=CACHE_FILE, tags_file=TAGS_FILE, manifest=self.manifest)
            self.library.player_widget = self.player
            self.player.set_library_tab(self.library)
            self.views["library"] = self.library

            from ui.downloads_tab import DownloadsTab
            self.downloads_view = DownloadsTab(
                self.content_area,
                config_manager=self.config_manager,
                manifest=self.manifest,
                player_widget=self.player,
            )
            self.views["downloads"] = self.downloads_view

            from ui.ignored_tab import IgnoredTab
            self.ignored_view = IgnoredTab(self.content_area, manifest=self.manifest)
            self.views["ignored"] = self.ignored_view

            # --- New Tabs ---
            from ui.dashboard import DashboardTab
            from ui.vault import VaultTab
            
            self.dashboard = DashboardTab(self.content_area, library_tab=self.library)
            self.views["dashboard"] = self.dashboard
            
            self.vault = VaultTab(self.content_area)
            self.views["vault"] = self.vault
            
            # Create Lyrics Panel (hidden by default)
            from ui.lyrics import LyricsPanel
            self.lyrics_panel = LyricsPanel(self)
            self.lyrics_panel.grid(row=0, column=2, rowspan=2, sticky="ns")
            self.lyrics_panel.grid_remove()  # Start hidden
            self.lyrics_panel.is_visible = False
            
            # Connect lyrics panel to player
            self.player.set_lyrics_panel(self.lyrics_panel)
            
            self.settings = SettingsTab(self.content_area, config_manager=self.config_manager, manifest=self.manifest)
            self.views["settings"] = self.settings

            # Connect Events
            self.library.bind("<<PlaySong>>", self.on_play_song)
            self.player.bind("<<TagsUpdated>>", lambda e: self.on_tags_updated(e))
            self.player.bind("<<TrackChanged>>", self.on_track_changed)
            
            self.player.set_mini_mode_callback(self.toggle_mini_mode)
            
            # Setup downloader signals
            if hasattr(self.downloader, 'downloader') and hasattr(self.downloader.downloader, 'signals'):
                 self.downloader.downloader.signals.download_complete.connect(self.on_download_complete)

            # Media Keys
            self.media_keys = MediaKeyHandler(self.player)
            self.media_keys.start()

        except Exception as e:
            print(f"Error initializing views: {e}")
            import traceback
            traceback.print_exc()
            
    def show_splash(self):
        """Show splash screen."""
        # Check for new splash first
        splash_path = resource_path("assets/NewSplash.png")
        if not os.path.exists(splash_path):
            # Fallback
            splash_path = resource_path("resources/splash.png")
            
        if not os.path.exists(splash_path):
            self.show_view("downloader")
            return
            
        # Create a top-level covering the window
        splash_window = ctk.CTkToplevel(self)
        splash_window.overrideredirect(True)
        
        # Center splash using Screen Dimensions
        # Match App Size
        w, h = 1100, 750
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = int((screen_width - w) / 2)
        y = int((screen_height - h) / 2)
        
        splash_window.geometry(f"{w}x{h}+{x}+{y}")
        splash_window.attributes("-topmost", True)
        
        try:
             pil_img = Image.open(splash_path)
             pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
             img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))
             label = ctk.CTkLabel(splash_window, image=img, text="")
             label.pack(fill="both", expand=True)
        except Exception:
             pass

        def end_splash():
            splash_window.destroy()
            self.deiconify()
            self.show_view("dashboard")
            # Changelog popup disabled — feels noisy on every version bump.
            # check_changelog() is kept defined below in case we want to wire
            # it back in selectively (e.g., only on major versions).

        self.after(2000, end_splash)

    def show_view(self, view_name):
        """Switch the central view."""
        # if view_name == "settings":
        #      # Original logic had a placeholder alert
        #      messagebox.showinfo("Settings", "Settings are currently located in the Downloader tab.\nDedicated settings page coming soon.")
        #      return
        


        if self.current_view:
            self.current_view.pack_forget()
        
        if view_name in self.views:
            view = self.views[view_name]
            view.pack(fill="both", expand=True)
            self.current_view = view
            self.sidebar.set_active(view_name)
            
            # Refresh Dashboard/Vault/Downloads/Ignored on view switch
            if view_name in ["dashboard", "vault", "downloads", "ignored"] and hasattr(view, 'refresh'):
                view.refresh()

            
            # Refresh Settings/Downloader to ensure sync
            if view_name == "settings" and hasattr(view, 'load_settings'):
                 view.load_settings()
            elif view_name == "downloader" and hasattr(view, 'load_config'):
                 view.load_config()
    
    def _run_path_migration(self):
        """One-shot migration from the legacy single `path` config key to the
        Downloads/Library two-path model + manifest. Idempotent — safe to run
        every launch; bails out if both new keys already exist."""
        c = self.config_manager
        legacy_path = c.get("path", "")
        downloads_path = c.get("downloads_path", "")
        library_path = c.get("library_path", "")

        if downloads_path and library_path:
            return  # Already migrated.

        if not legacy_path or not os.path.isdir(legacy_path):
            return  # No legacy path to migrate from; user will pick paths in Settings.

        # Both downloads and library default to the same folder — zero-disruption
        # for existing users; they can split later in Settings.
        if not downloads_path:
            c.set("downloads_path", legacy_path)
        if not library_path:
            c.set("library_path", legacy_path)

        # Bootstrap the manifest by scanning the existing library and recording
        # everything we find as `location=library`. Reuses the mtime-cached
        # ID3 walker added in Phase 1.
        if len(self.manifest) > 0:
            return  # Manifest already populated (e.g., partial prior migration).

        try:
            from core.utils import _scan_with_uuid_cache
            scanned = _scan_with_uuid_cache(legacy_path, (".mp3", ".wav"))
        except Exception as e:
            print(f"Migration scan failed: {e}")
            return

        added = 0
        for filepath, uuid in scanned.items():
            if not uuid:
                continue
            self.manifest.add(
                uuid,
                title=os.path.splitext(os.path.basename(filepath))[0],
                artist="",
                filepath=filepath,
                location=LOCATION_LIBRARY,
            )
            added += 1
        self.manifest.flush()
        print(f"Migration: imported {added} existing UUIDs from {legacy_path} into the manifest.")

    def check_changelog(self):
        """Show changelog on first launch of new version."""
        current_version = APP_VERSION
        last_version = None
        state_file = "window_state.json"
        data = {}

        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                    last_version = data.get("version")
            except (json.JSONDecodeError, OSError):
                pass

        if last_version != current_version:
            messagebox.showinfo(
                f"What's New in v{current_version}",
                f"🎉 Welcome to SunoSync v{current_version}! 🎉\n\n"
                "• Redesigned UI with CustomTkinter\n"
                "• Improved Stability\n"
                "• Better Configuration Management",
            )

            data["version"] = current_version
            try:
                with open(state_file, "w") as f:
                    json.dump(data, f)
            except OSError:
                pass

    def load_window_state(self):
        try:
            if os.path.exists("window_state.json"):
                with open("window_state.json", "r") as f:
                    data = json.load(f)
                    geometry = data.get("geometry", "1100x750")
                    self.geometry(geometry)
        except (json.JSONDecodeError, OSError):
            pass

    def on_close(self):
        try:
            with open("window_state.json", "w") as f:
                json.dump({"geometry": self.geometry()}, f)
        except OSError:
             pass
             
        if "downloader" in self.views:
             # Assuming downloader has on_close/cleanup
             try:
                 if hasattr(self.views["downloader"], "on_close"):
                    self.views["downloader"].on_close()
             except:
                pass
                
        if hasattr(self, 'media_keys'):
            self.media_keys.stop()

        if hasattr(self, 'token_server'):
            self.token_server.stop()

        if hasattr(self, 'config_manager'):
            try:
                self.config_manager.flush()
            except Exception:
                pass

        if hasattr(self, 'manifest'):
            try:
                self.manifest.flush()
            except Exception:
                pass

        self.destroy()
        sys.exit()

    def on_download_complete(self, success):
        # Delay refresh to prevent TclError when widgets are being created/destroyed
        if success and self.library:
            # Cancel any pending refresh
            if hasattr(self, '_refresh_timer') and self._refresh_timer:
                self.after_cancel(self._refresh_timer)
            # Schedule refresh for 2 seconds later
            self._refresh_timer = self.after(2000, self._delayed_library_refresh)
    
    def _delayed_library_refresh(self):
        if self.library and hasattr(self.library, 'refresh_library'):
            try:
                self.library.refresh_library()
            except Exception as e:
                print(f"Library refresh error: {e}")

    def _on_extension_token(self, token):
        """Callback fired when Chrome extension pushes a new token."""
        try:
            # Update config
            self.config_manager.set("token", token)
            self.config_manager.save_config()
            
            # Update downloader tab UI (must run on main thread)
            if hasattr(self, 'downloader') and hasattr(self.downloader, 'set_token_from_extension'):
                self.after(0, lambda t=token: self.downloader.set_token_from_extension(t))
        except Exception as e:
            print(f"Extension token callback error: {e}")

    def on_play_song(self, event):
        if hasattr(self.library, 'current_playlist') and hasattr(self.library, 'current_index'):
            self.player.set_playlist(self.library.current_playlist, self.library.current_index)

    def on_tags_updated(self, event):
        self.after(200, self._safe_reload_tags)
        
    def _safe_reload_tags(self):
        if self.library and hasattr(self.library, 'reload_tags'):
            self.library.reload_tags()

    def on_track_changed(self, event):
        self.after(50, lambda: self._update_library_selection())

    def _update_library_selection(self):
        if self.player and hasattr(self.player, 'current_file') and self.player.current_file:
            try:
                filepath = os.path.normpath(self.player.current_file)
                self.library.select_song(filepath)
            except:
                pass

    
    def toggle_mini_mode(self):
        if not hasattr(self, 'is_mini_mode'): self.is_mini_mode = False
        
        if not self.is_mini_mode:
            # Enter Mini Mode
            self.is_mini_mode = True
            self.last_geometry = self.geometry()
            
            # Hide Main Layout
            self.sidebar.grid_remove()
            self.content_area.grid_remove()
            
            # Check lyrics panel visibility safely
            if hasattr(self, 'lyrics_panel') and self.lyrics_panel.winfo_viewable():
                self.lyrics_panel.grid_remove()
            
            # Unlock resizing constraints
            self.minsize(500, 80)
            
            # Move player to top and fill
            self.player.grid(row=0, column=0, columnspan=3, sticky="nsew")
            
            # Adjust Row Weights (Row 0 gets all weight)
            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=0)
            
            # Frameless Mode
            self.overrideredirect(True)
            
            # Resize Window to Compact Strip (Standard Banner Size)
            self.geometry("600x80")
            self.attributes("-topmost", True)
            
            self.player.set_mini_btn_icon(True)
            self.update_idletasks()
            
        else:
            # Exit Mini Mode
            self.is_mini_mode = False
            
            # Restore Layout
            self.overrideredirect(False)
            
            # Restore Player Position (Bottom)
            self.player.grid(row=1, column=0, columnspan=2, sticky="ew")
            
            # Restore Row Weights (Content gets weight)
            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=0)
            
            # Restore Layout Frames
            self.sidebar.grid()
            self.content_area.grid()
            
            # Restore Lyrics if was visible
            if hasattr(self, 'lyrics_panel') and hasattr(self.lyrics_panel, 'is_visible') and self.lyrics_panel.is_visible:
                self.lyrics_panel.grid()
                
            # Restore Size constraints
            self.minsize(1000, 750)
            
            # Restore Geometry
            if hasattr(self, 'last_geometry'):
                self.geometry(self.last_geometry)
            self.attributes("-topmost", False)
            
            self.player.set_mini_btn_icon(False)



if __name__ == "__main__":
    # High DPI fix
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = SunoSyncApp()
    app.mainloop()
