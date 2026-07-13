import tkinter as tk


class ToolTip:
    """
    Create a tooltip for a given widget with hover behavior.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        
        # Bind events to widget and all children
        self.widget.bind("<Enter>", self.show_tooltip, add="+")
        self.widget.bind("<Leave>", self.hide_tooltip, add="+")
        self.widget.bind("<Button>", self.hide_tooltip, add="+")
        
        # Also bind to children to prevent glitches
        for child in self.widget.winfo_children():
            child.bind("<Enter>", self.show_tooltip, add="+")
            child.bind("<Leave>", self.hide_tooltip, add="+")
    
    def show_tooltip(self, event=None):
        """Display the tooltip."""
        if self.tooltip_window or not self.text:
            return
        
        # Get widget position
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() - 30  # Above the widget
        
        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # No window decorations
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Create label with text
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background="#252526",
            foreground="white",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
            padx=8,
            pady=4,
            wraplength=300  # Wrap long text
        )
        label.pack()
    
    def hide_tooltip(self, event=None):
        """Hide the tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_text(self, new_text):
        """Update tooltip text."""
        self.text = new_text
