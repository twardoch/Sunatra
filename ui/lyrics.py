import customtkinter as ctk
import os


class LyricsPanel(ctk.CTkFrame):
    """Side panel for displaying song lyrics."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=300, fg_color="#252526", **kwargs)
        
        self.is_visible = False
        self.current_lyrics = ""
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        title_label = ctk.CTkLabel(header, text="🎤 Lyrics", font=("Segoe UI", 16, "bold"))
        title_label.pack(side="left")
        
        close_btn = ctk.CTkButton(header, text="✕", width=30, height=30, 
                                   fg_color="transparent", hover_color="#f44336",
                                   command=self.hide, font=("Segoe UI", 16))
        close_btn.pack(side="right")
        
        # Lyrics display area (scrollable)
        self.lyrics_text = ctk.CTkTextbox(self, wrap="word", font=("Segoe UI", 12),
                                          fg_color="#2d2d30", text_color="#e0e0e0",
                                          activate_scrollbars=True)
        self.lyrics_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Make read-only
        self.lyrics_text.configure(state="disabled")
        
        # Show placeholder initially
        self.show_placeholder()
    
    def show_placeholder(self):
        """Show 'No Lyrics Found' placeholder."""
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", "\n\n\n        No Lyrics Found\n\n    Play a song with lyrics to view them here")
        self.lyrics_text.tag_add("center", "1.0", "end")
        self.lyrics_text.tag_config("center", justify="center", foreground="#6a6a6e")
        self.lyrics_text.configure(state="disabled")
    
    def show_lyrics(self, lyrics_text):
        """Display lyrics in the panel."""
        self.current_lyrics = lyrics_text
        
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        
        if lyrics_text and lyrics_text.strip():
            # Clean up escaped newlines
            lyrics_text = lyrics_text.replace('\\n', '\n')
            # Display actual lyrics
            self.lyrics_text.insert("1.0", lyrics_text)
            self.lyrics_text.tag_add("lyrics", "1.0", "end")
            self.lyrics_text.tag_config("lyrics", justify="left", foreground="#e0e0e0")
        else:
            # Show placeholder
            self.show_placeholder()
            return
        
        self.lyrics_text.configure(state="disabled")
        # Scroll to top
        self.lyrics_text.see("1.0")
    
    def update_from_song(self, song_data):
        """Update lyrics from song metadata."""
        if not song_data:
            self.show_placeholder()
            return
        
        # Try to get lyrics from song data
        lyrics = song_data.get('lyrics', '')
        
        # If no lyrics in metadata, try .txt file
        if not lyrics or not lyrics.strip():
            filepath = song_data.get('filepath', '')
            if filepath:
                txt_path = os.path.splitext(filepath)[0] + ".txt"
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            lyrics = f.read()
                    except Exception:
                        pass
        
        self.show_lyrics(lyrics)
    
    def toggle(self):
        """Toggle panel visibility."""
        if self.is_visible:
            self.hide()
        else:
            self.show()
    
    def show(self):
        """Show the panel."""
        if not self.is_visible:
            self.grid()  # Re-show using grid
            self.is_visible = True
    
    def hide(self):
        """Hide the panel."""
        if self.is_visible:
            self.grid_remove()  # Hide but keep grid position
            self.is_visible = False
