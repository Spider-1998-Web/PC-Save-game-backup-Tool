# theme.py - Fixed version

import customtkinter as ctk

# ======== Color Palette ========
COLORS = {
    "primary": "#3498db",      # Soft blue (changed from intense red)
    "secondary": "#2980b9",    # Darker blue for hover
    "accent": "#1abc9c",       # Teal accent for selection
    "text": "#FFFFFF",         # White
    "background": "#1A1A1A",   # Near-black
    "surface": "#333333",      # Dark gray
    "error": "#e74c3c"         # Error/warning color
}

# ======== Typography ========
FONTS = {
    "title": ("Arial", 18, "bold"),
    "body": ("Arial", 14),
    "button": ("Arial", 14, "bold"),
    "label": ("Arial", 12)
}

# ======== Component Styles ========
STYLES = {
    "button": {
        "fg_color": COLORS["primary"],
        "hover_color": COLORS["secondary"],
        "text_color": COLORS["text"],
        "corner_radius": 8
    },
    "frame": {
        "fg_color": COLORS["background"],
        "border_width": 0
    },
    "entry": {
        "fg_color": COLORS["surface"],
        "text_color": COLORS["text"],
        "border_color": COLORS["primary"],
        "border_width": 1,
        "corner_radius": 6
    },
    "label": {
        "text_color": COLORS["text"],
        "corner_radius": 0
    },
    "scrollbar": {
        "button_color": COLORS["primary"],
        "button_hover_color": COLORS["secondary"]
    }
}

def configure_theme():
    ctk.set_appearance_mode("Dark")
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    
    # Set default colors for CTk
    ctk.set_default_color_theme("dark-blue")  # Base with our custom colors
  
