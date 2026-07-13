from PIL import ImageFont


class ThemeManager:
    def __init__(self):
        # --- Dubhaimid Dark Palette (house "corporate" MUI theme) ---
        # Mirrors hyb-electron-template/src/renderer/src/themes/dubhaimid.ts:
        # neutral charcoal surfaces, light-gray text, a single muted steel-blue
        # accent, flat borders, no shadows. Tkinter can't do rgba, so the
        # translucent MUI dividers/borders are flattened to opaque hex here.
        self.bg_dark = "#1e1e1e"        # background.default
        self.bg_sidebar = "#1a1a1b"     # paperDark (sidebar, darkest surface)
        self.card_bg = "#252526"        # paper (cards, panels)
        self.bg_card = self.card_bg     # Alias
        self.bg_input = "#2d2d30"       # paperLight (input fields)
        self.hover_row = "#2a2a2b"      # tableDark (row hover highlight)
        self.player_bg = "#1a1a1b"      # paperDark (player bar background)

        self.fg_primary = "#e0e0e0"     # text.primary (light gray, not pure white)
        self.fg_secondary = "#9aa0a6"   # text.secondary

        # Accent kept under the legacy *_purple names so existing call sites
        # keep working, but the value is now the Dubhaimid steel-blue primary.
        self.accent_purple = "#5c8bc4"        # primary.main
        self.accent_purple_hover = "#3f6a9e"  # primary.dark (hover)
        self.accent_pink = "#82a9d6"    # secondary accent -> primary.light
        self.accent_red = "#f44336"     # error / destructive
        self.accent_green = "#66bb6a"   # success / keep
        self.accent_yellow = "#ffa726"  # warning / star / favorite

        # Chrome navy shared by both corporate themes (title-bar family color).
        self.accent_navy = "#0a246a"        # secondary.main
        self.accent_navy_light = "#2f4f8f"  # secondary.light

        self.border_subtle = "#3a3a3d"  # divider (rgba(255,255,255,0.12) flattened)
        self.card_border = "#3a3a3d"    # Card borders
        self.pill_inactive = "#3e3e42"  # chip background / inactive pill

        # --- Typography (Segoe UI — matches the house plainTypography stack) ---
        self.font_family = "Segoe UI"
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
