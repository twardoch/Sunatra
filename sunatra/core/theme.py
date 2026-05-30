from PIL import ImageFont


class ThemeManager:
    def __init__(self):
        # --- Spotify-Inspired Dark Mode Palette ---
        self.bg_dark = "#121212"        # Main background
        self.bg_sidebar = "#0a0a0a"     # Sidebar background (darker)
        self.card_bg = "#181818"        # Elevated surfaces (cards, panels)
        self.bg_card = self.card_bg     # Alias
        self.bg_input = "#272727"       # Input fields
        self.hover_row = "#2A2A2A"      # Row hover highlight
        self.player_bg = "#181818"      # Player bar background

        self.fg_primary = "#FFFFFF"     # Pure white — headers, active items
        self.fg_secondary = "#B3B3B3"   # Light gray — secondary text, inactive items

        self.accent_purple = "#8B5CF6"  # Primary action (Vibrant Violet)
        self.accent_purple_hover = "#7C3AED"  # Hover state
        self.accent_pink = "#EC4899"    # Secondary accent
        self.accent_red = "#EF4444"     # Destructive action
        self.accent_green = "#22C55E"   # Success / Keep
        self.accent_yellow = "#EAB308"  # Star / Favorite

        self.border_subtle = "#333333"  # Subtle borders
        self.card_border = "#333333"    # Card borders
        self.pill_inactive = "#333333"  # Inactive pill/chip background

        # --- Typography (Inter with Segoe UI fallback) ---
        self.font_family = "Inter"
        self.font_fallback = "Segoe UI"

        self.section_font = (self.font_family, 11, "bold")
        self.title_font = (self.font_family, 24, "bold")
        self.mono_font = ("Consolas", 10)
        self.nav_font = (self.font_family, 11, "bold")
        self.body_font = (self.font_family, 12)
        self.small_font = (self.font_family, 10)

    def load_title_font(self, size):
        # Fallback to arial for PIL rendering
        return ImageFont.truetype("arial.ttf", size)

    def apply_treeview_style(self):
        import tkinter.ttk as ttk
        style = ttk.Style()

        # 'clam' theme supports background color customization better than default Windows theme
        try:
            style.theme_use("clam")
        except:
            pass

        # Configure Treeview colors
        style.configure("Treeview",
                        background=self.card_bg,
                        foreground=self.fg_primary,
                        fieldbackground=self.card_bg,
                        borderwidth=0,
                        font=self.section_font)

        # Map selection color to Purple
        style.map("Treeview",
                  background=[("selected", self.accent_purple)],
                  foreground=[("selected", "white")])

        # Heading
        style.configure("Treeview.Heading",
                        background=self.card_bg,
                        foreground=self.fg_secondary,
                        relief="flat",
                        font=self.nav_font)
        style.map("Treeview.Heading",
                  background=[("active", self.bg_input)])
