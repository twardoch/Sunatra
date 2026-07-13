import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    """Left sidebar navigation — Spotify-style."""
    def __init__(self, parent, on_navigate, **kwargs):
        super().__init__(parent, width=220, corner_radius=0,
                         fg_color="#1a1a1b", **kwargs)

        self.on_navigate = on_navigate
        self.buttons = {}
        self.indicators = {}

        self._create_widgets()

    def _create_widgets(self):
        # --- Header Area (Logo + Mini Settings) ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(20, 10), padx=15)
        
        # Logo
        logo_label = ctk.CTkLabel(header_frame, text="SunoSync",
                                  font=("Segoe UI", 20, "bold"),
                                  text_color="#FFFFFF")
        logo_label.pack(side="left")
        
        # Mini Settings Icon (Redundant access)
        settings_btn = ctk.CTkButton(header_frame, text="⚙", width=24, height=24,
                                     fg_color="transparent", hover_color="#3a3a3d",
                                     font=("Segoe UI", 14), text_color="#9aa0a6",
                                     command=lambda: self.handle_click("settings"))
        settings_btn.pack(side="right")

        # Thin separator under logo
        ctk.CTkFrame(self, height=1, fg_color="#3a3a3d").pack(fill="x", padx=15, pady=(0, 10))

        # --- Navigation Container (Top, Expands) ---
        self.nav_container = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_container.pack(side="top", fill="both", expand=True, anchor="n")

        # --- Bottom Container (Settings, Fixed) ---
        self.bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_container.pack(side="bottom", fill="x", pady=(0, 10))

        # Navigation Items (Top)
        self._add_nav_item("Dashboard", "🏠", "dashboard", parent=self.nav_container)
        self._add_nav_item("Downloader", "⬇", "downloader", parent=self.nav_container)
        self._add_nav_item("Downloads", "📥", "downloads", parent=self.nav_container)
        self._add_nav_item("Library", "🎵", "library", parent=self.nav_container)
        self._add_nav_item("Ignored", "🚫", "ignored", parent=self.nav_container)
        self._add_nav_item("Prompt Vault", "📓", "vault", parent=self.nav_container)
        
        # Settings (Bottom)
        self._add_nav_item("Settings", "⚙", "settings", parent=self.bottom_container)

    def set_active(self, view_name):
        """Update active state of buttons — white text + purple left border + background."""
        for name, btn in self.buttons.items():
            if name == view_name:
                # Active: bg-violet-500/10 (matched approx color #26333f from FilterBar)
                btn.configure(fg_color="#26333f",
                              text_color="#FFFFFF")
                # Show purple indicator
                if name in self.indicators:
                    self.indicators[name].configure(fg_color="#5c8bc4")
            else:
                btn.configure(fg_color="transparent",
                              text_color="#9aa0a6")
                # Hide indicator
                if name in self.indicators:
                    self.indicators[name].configure(fg_color="transparent")

    # --- Wrapper for Navigation with Limits ---
    def handle_click(self, view_name):
        # UNLOCKED: All features available in paid EXE
        self.on_navigate(view_name)

    def _add_nav_item(self, text, icon, view_name, parent=None, bottom=False):
        target = parent if parent else self
        
        # Container frame for indicator + button
        # Reduced height for tighter feel (32px)
        item_frame = ctk.CTkFrame(target, fg_color="transparent", height=32)

        # Purple left border indicator
        indicator = ctk.CTkFrame(item_frame, width=4, fg_color="transparent",
                                 corner_radius=2)
        indicator.pack(side="left", fill="y", padx=(0, 0), pady=4)
        self.indicators[view_name] = indicator

        # Navigation button
        btn = ctk.CTkButton(item_frame,
                            text=f"  {icon}  {text}",
                            anchor="w",
                            command=lambda: self.handle_click(view_name),
                            fg_color="transparent",
                            text_color="#9aa0a6",
                            hover_color="#2a2a2b",
                            height=28,
                            font=("Segoe UI", 13))

        btn.pack(side="left", fill="x", expand=True, padx=(3, 10))

        # Just pack normally in the target container
        item_frame.pack(fill="x", pady=0, padx=5)

        self.buttons[view_name] = btn
