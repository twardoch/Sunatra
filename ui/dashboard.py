
import customtkinter as ctk


class StatCard(ctk.CTkFrame):
    """A card displaying a single statistic — rounded dark card."""
    def __init__(self, parent, title, sorted_string, icon, **kwargs):
        super().__init__(parent, fg_color="#181818", corner_radius=12, **kwargs)

        # Icon
        self.icon_lbl = ctk.CTkLabel(self, text=icon, font=("Inter", 32))
        self.icon_lbl.pack(side="left", padx=(20, 10))

        # Text Frame
        self.text_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.text_frame.pack(side="left", pady=15)

        self.value_lbl = ctk.CTkLabel(self.text_frame, text=sorted_string,
                                      font=("Inter", 24, "bold"),
                                      text_color="#FFFFFF", anchor="w")
        self.value_lbl.pack(anchor="w")

        self.title_lbl = ctk.CTkLabel(self.text_frame, text=title,
                                      font=("Inter", 12),
                                      text_color="#B3B3B3", anchor="w")
        self.title_lbl.pack(anchor="w")

    def update_value(self, value):
        self.value_lbl.configure(text=str(value))


class DashboardTab(ctk.CTkFrame):
    """Producer Dashboard / Home Tab."""

    def __init__(self, parent, library_tab, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.library_tab = library_tab

        self.stat_cards = {}

        # 1. Header
        self.header = ctk.CTkLabel(self, text="Producer Dashboard",
                                   font=("Inter", 28, "bold"),
                                   text_color="#FFFFFF")
        self.header.pack(pady=(20, 10), padx=30, anchor="w")

        # 2. Stats Grid
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="x", padx=20, pady=10)
        self.grid_frame.grid_columnconfigure((0, 1), weight=1)

        # Card 1: Total Tracks
        self.card_tracks = StatCard(self.grid_frame, "Total Tracks", "0", "🎵")
        self.card_tracks.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # Card 2: Total Duration
        self.card_duration = StatCard(self.grid_frame, "Total Playtime", "00h 00m", "⏱️")
        self.card_duration.grid(row=0, column=1, sticky="ew", padx=10, pady=10)

        # Card 3: Storage
        self.card_storage = StatCard(self.grid_frame, "Storage Used", "0 GB", "💾")
        self.card_storage.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        # Card 4: Top Genre
        self.card_genre = StatCard(self.grid_frame, "Top Genre", "--", "🔥")
        self.card_genre.grid(row=1, column=1, sticky="ew", padx=10, pady=10)

        # 3. Recent Activity Header
        self.recent_lbl = ctk.CTkLabel(self, text="Recently Downloaded",
                                       font=("Inter", 20, "bold"),
                                       text_color="#FFFFFF")
        self.recent_lbl.pack(pady=(30, 10), padx=30, anchor="w")

        # 4. Recent List
        self.recent_frame = ctk.CTkFrame(self, fg_color="#181818", corner_radius=12)
        self.recent_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))

        # Initial stats
        self.refresh()

    def get_stats(self):
        """Calculate stats from library data."""
        songs = self.library_tab.all_songs

        count = len(songs)

        # Duration
        total_seconds = sum(s.get('duration', 0) for s in songs)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours)}h {int(minutes)}m"

        # Storage
        total_bytes = sum(s.get('filesize', 0) for s in songs)
        gb = total_bytes / (1024 * 1024 * 1024)
        if gb < 1:
            mb = total_bytes / (1024 * 1024)
            storage_str = f"{mb:.1f} MB"
        else:
            storage_str = f"{gb:.2f} GB"

        # Top Genre
        genres = [s.get('genre', '--') for s in songs if s.get('genre') and s.get('genre') != '--']
        if genres:
            from collections import Counter
            most_common = Counter(genres).most_common(1)
            top_genre = most_common[0][0] if most_common else "N/A"
        else:
            top_genre = "N/A"

        return count, duration_str, storage_str, top_genre

    def refresh(self):
        """Recalculate and update UI."""
        count, dur, store, genre = self.get_stats()

        self.card_tracks.update_value(str(count))
        self.card_duration.update_value(dur)
        self.card_storage.update_value(store)
        self.card_genre.update_value(genre[:15] + "..." if len(genre) > 15 else genre)

        # Update Recent List
        for widget in self.recent_frame.winfo_children():
            widget.destroy()

        try:
            sorted_songs = sorted(self.library_tab.all_songs, key=lambda x: x.get('date', '0000'), reverse=True)
            recents = sorted_songs[:5]

            for i, song in enumerate(recents):
                row = ctk.CTkFrame(self.recent_frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=5)

                title = song.get('title', 'Unknown')
                if len(title) > 40: title = title[:37] + "..."
                ctk.CTkLabel(row, text=title, font=("Inter", 14, "bold"),
                             text_color="#FFFFFF", width=300, anchor="w").pack(side="left")

                artist = song.get('artist', 'Unknown')
                if len(artist) > 20: artist = artist[:17] + "..."
                ctk.CTkLabel(row, text=artist, width=150, anchor="w",
                             text_color="#B3B3B3", font=("Inter", 12)).pack(side="left")

                date = song.get('date', '--')
                ctk.CTkLabel(row, text=date, width=100, anchor="e",
                             text_color="#B3B3B3", font=("Inter", 12)).pack(side="right")

                if i < len(recents) - 1:
                    ctk.CTkFrame(self.recent_frame, height=1, fg_color="#333333").pack(fill="x", padx=10)
        except Exception as e:
            print(f"Error updating recent list: {e}")
