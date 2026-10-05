"""Theme definitions and Apple Frosted Glass design system."""

# Apple Frosted Glass Color System
ACCENT_ORANGE = "#ea580c"
ACCENT_ORANGE_HOVER = "#f97316"
ACCENT_ORANGE_ACTIVE = "#c2410c"

HEALTHY = "#10b981"         # Emerald Green for CONNECTED & Online
HEALTHY_LIGHT = "rgba(16, 185, 129, 0.12)"
WARNING = "#f59e0b"         # Amber
CRITICAL = "#ef4444"        # Red

SLATE_TITLE = "#0f172a"     # Main dark headers & terminal text
SLATE_TEXT = "#1e293b"      # Body text
SLATE_MUTED = "#64748b"     # Subtitle & hints
SLATE_FAINT = "#94a3b8"     # Tertiary & icons
SLATE_BORDER = "#cbd5e1"    # Slider inactive track

# Frosted Glass Translucencies
FROSTED_BG = "rgba(232, 236, 238, 0.90)"
FROSTED_MODAL = "rgba(226, 231, 234, 0.95)"
FROSTED_OVERLAY = "rgba(15, 23, 42, 0.35)"
FROSTED_CARD = "rgba(255, 255, 255, 0.65)"
FROSTED_CARD_HOVER = "rgba(255, 255, 255, 0.88)"
FROSTED_INPUT = "rgba(255, 255, 255, 0.92)"
FROSTED_BORDER = "rgba(255, 255, 255, 0.70)"
HAIRLINE = "rgba(0, 0, 0, 0.08)"

RADIUS_MODAL = 20
RADIUS_CARD = 14
RADIUS_BTN = 10

# Compatibility Aliases
ACCENT = ACCENT_ORANGE
BORDER_SOFT = "rgba(0, 0, 0, 0.08)"
PANEL_FILL = "rgba(255, 255, 255, 0.7)"
SURFACE_BG = FROSTED_BG
SURFACE_CARD = FROSTED_CARD
SURFACE_HOVER = FROSTED_CARD_HOVER
SURFACE_ACTIVE = "rgba(255, 255, 255, 0.95)"
TEXT_1 = SLATE_TITLE
TEXT_2 = SLATE_TEXT
TEXT_3 = SLATE_MUTED

MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {FROSTED_BG};
    color: {SLATE_TEXT};
}}

QWidget {{
    color: {SLATE_TEXT};
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: rgba(100, 116, 139, 0.35);
    min-height: 24px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(100, 116, 139, 0.6);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Frosted Cards */
QFrame#Card {{
    background-color: {FROSTED_CARD};
    border: 1px solid {FROSTED_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* Primary Buttons (Apple Orange) */
QPushButton.PrimaryBtn {{
    background-color: {ACCENT_ORANGE};
    color: #ffffff;
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton.PrimaryBtn:hover {{
    background-color: {ACCENT_ORANGE_HOVER};
}}
QPushButton.PrimaryBtn:pressed {{
    background-color: {ACCENT_ORANGE_ACTIVE};
}}
QPushButton.PrimaryBtn:disabled {{
    background-color: rgba(203, 213, 225, 0.6);
    color: {SLATE_FAINT};
}}

/* Secondary / Pill Buttons */
QPushButton.PillBtn {{
    background-color: #ffffff;
    color: {SLATE_TEXT};
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 13px;
}}
QPushButton.PillBtn:hover {{
    background-color: {FROSTED_CARD_HOVER};
    border-color: rgba(0, 0, 0, 0.15);
}}

/* Danger Buttons */
QPushButton.DangerBtn {{
    background-color: transparent;
    color: {CRITICAL};
    border: 1px solid {CRITICAL};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton.DangerBtn:hover {{
    background-color: {CRITICAL};
    color: #ffffff;
}}

/* Ghost Buttons */
QPushButton.GhostBtn {{
    background-color: transparent;
    color: {SLATE_MUTED};
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 14px;
}}
QPushButton.GhostBtn:hover {{
    color: {SLATE_TITLE};
    background-color: rgba(0, 0, 0, 0.04);
}}

/* Inputs and Forms */
QLineEdit, QComboBox {{
    background-color: {FROSTED_INPUT};
    color: {SLATE_TEXT};
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: {RADIUS_BTN}px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT_ORANGE};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT_ORANGE};
}}
QLineEdit[mono="true"] {{
    font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
    font-size: 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    color: {SLATE_TEXT};
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    selection-background-color: rgba(234, 88, 12, 0.1);
    selection-color: {ACCENT_ORANGE};
}}

/* Form Section Labels */
QLabel.FormSectionLabel {{
    font-size: 11px;
    font-weight: 700;
    color: {SLATE_MUTED};
    letter-spacing: 0.6px;
}}

/* Hairline Separator */
QFrame#Hairline {{
    background-color: {HAIRLINE};
    max-height: 1px;
    border: none;
}}
"""
