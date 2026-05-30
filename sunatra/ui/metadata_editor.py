import os
from tkinter import messagebox

import customtkinter as ctk


class MetadataEditorDialog(ctk.CTkToplevel):
    """Dialog for editing song metadata."""

    def __init__(self, parent, song_data, on_save_callback=None):
        super().__init__(parent)

        self.song_data = song_data
        self.on_save_callback = on_save_callback

        # Window setup
        self.title("Edit Metadata")
        self.geometry("500x600")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (500 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        # Header
        header = ctk.CTkLabel(self, text="Edit Song Metadata", font=("Inter", 18, "bold"))
        header.pack(pady=(20, 10))

        # Scrollable content
        scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Create entry fields for all editable metadata
        self.entries = {}

        editable_fields = [
            ("title", "Title"),
            ("artist", "Artist"),
            ("genre", "Genre"),
            ("bpm", "BPM"),
            ("prompt", "Prompt"),
            ("lyrics", "Lyrics (multiline)")
        ]

        for field_key, field_label in editable_fields:
            # Label
            label = ctk.CTkLabel(scroll_frame, text=field_label, anchor="w", font=("Inter", 12, "bold"))
            label.pack(anchor="w", pady=(10, 2))

            # Entry or Textbox
            if field_key == "lyrics" or field_key == "prompt":
                # Multiline textbox
                entry = ctk.CTkTextbox(scroll_frame, height=100, font=("Inter", 11))
                entry.pack(fill="x", pady=(0, 5))

                # Insert current value
                current_value = self.song_data.get(field_key, "")
                if current_value:
                    entry.insert("1.0", current_value)
            else:
                # Single line entry
                entry = ctk.CTkEntry(scroll_frame, font=("Inter", 11))
                entry.pack(fill="x", pady=(0, 5))

                # Insert current value
                current_value = self.song_data.get(field_key, "")
                if current_value and current_value != "--":
                    entry.insert(0, str(current_value))

            self.entries[field_key] = entry

        # Read-only info
        info_frame = ctk.CTkFrame(scroll_frame, fg_color="#27272a")
        info_frame.pack(fill="x", pady=10)

        filepath = self.song_data.get("filepath", "Unknown")
        filename = os.path.basename(filepath) if filepath else "Unknown"

        info_label = ctk.CTkLabel(info_frame, text=f"File: {filename}",
                                  font=("Inter", 10), text_color="#a1a1aa", anchor="w")
        info_label.pack(padx=10, pady=5, anchor="w")

        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy,
                                    fg_color="transparent", border_width=1, width=100)
        cancel_btn.pack(side="left", padx=5)

        save_btn = ctk.CTkButton(button_frame, text="Save Changes", command=self.save_changes,
                                 fg_color="#7c3aed", hover_color="#6d28d9", width=150)
        save_btn.pack(side="right", padx=5)

    def save_changes(self):
        """Save metadata changes to file."""
        try:
            # Collect values from entries
            updated_data = {}

            for field_key, entry_widget in self.entries.items():
                if isinstance(entry_widget, ctk.CTkTextbox):
                    # Get text from textbox
                    value = entry_widget.get("1.0", "end-1c").strip()
                else:
                    # Get text from entry
                    value = entry_widget.get().strip()

                updated_data[field_key] = value

            # Write to file using suno_utils
            filepath = self.song_data.get("filepath")
            if filepath and os.path.exists(filepath):
                from sunatra.core.utils import save_metadata_to_file

                if save_metadata_to_file(filepath, updated_data):
                    messagebox.showinfo("Success", "Metadata updated successfully!")

                    # Call callback if provided
                    if self.on_save_callback:
                        self.on_save_callback(updated_data)

                    self.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save metadata to file.")
            else:
                messagebox.showerror("Error", "File not found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save metadata: {e}")
