class VisualStyles:
    """
    Visual styling constants for different diff elements.
    """
    
    # Color codes for different change types
    COLORS = {
        "addition": {
            "terminal": "\033[92m",  # Bright green
            "markdown": "green",
            "html": "#2cbe4e"
        },
        "deletion": {
            "terminal": "\033[91m",  # Bright red
            "markdown": "red",
            "html": "#cb2431"
        },
        "modification": {
            "terminal": "\033[93m",  # Bright yellow
            "markdown": "yellow",
            "html": "#f1e05a"
        },
        "breaking": {
            "terminal": "\033[31m",  # Red
            "markdown": "red",
            "html": "#d73a49"
        },
        "deprecated": {
            "terminal": "\033[95m",  # Magenta
            "markdown": "purple",
            "html": "#b392f0"
        },
        "info": {
            "terminal": "\033[96m",  # Cyan
            "markdown": "blue",
            "html": "#0366d6"
        },
        "highlight": {
            "terminal": "\033[1m",  # Bold
            "markdown": "**",  # Bold
            "html": "font-weight: bold"
        },
        "reset": {
            "terminal": "\033[0m",
            "markdown": "",
            "html": ""
        }
    }
    
    # Symbols for different change types
    SYMBOLS = {
        "addition": "+",
        "deletion": "-",
        "modification": "~",
        "breaking": "!",
        "deprecated": "⚠",
        "no_change": " ",
    }
    
    # Icons for markdown/HTML output
    ICONS = {
        "addition": "➕",
        "deletion": "➖",
        "modification": "🔄",
        "breaking": "⚠️",
        "deprecated": "⏳",
        "info": "ℹ️",
    }