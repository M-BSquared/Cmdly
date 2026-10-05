"""Tesla-inspired Dark Smoked Frosted Glass design system."""

# Tesla Cyber / Automotive Minimalist Palette
TESLA_BG = "rgba(9, 10, 14, 0.95)"
TESLA_CARD = "rgba(18, 21, 28, 0.75)"
TESLA_CARD_HOVER = "rgba(28, 33, 44, 0.85)"
TESLA_CARD_ACTIVE = "rgba(36, 42, 56, 0.95)"
TESLA_INPUT = "rgba(14, 16, 22, 0.85)"
TESLA_MODAL = "rgba(14, 17, 23, 0.96)"
TESLA_OVERLAY = "rgba(4, 5, 8, 0.65)"

# Hairlines and Borders
TESLA_BORDER = "rgba(255, 255, 255, 0.09)"
TESLA_BORDER_HOVER = "rgba(255, 255, 255, 0.20)"
TESLA_BORDER_ACTIVE = "rgba(56, 189, 248, 0.50)"
HAIRLINE = "rgba(255, 255, 255, 0.07)"

# Typography Colors
TEXT_TITLE = "#f8fafc"       # Crisp Pure White
TEXT_BODY = "#e2e8f0"        # High Contrast Silver
TEXT_MUTED = "#94a3b8"       # Telemetry Gray
TEXT_FAINT = "#64748b"       # Subtle Muted

# Accents (Tesla Cyber Blue & Status Glows)
ACCENT_CYAN = "#38bdf8"      # Electric Blue / Cyan
ACCENT_CYAN_HOVER = "#0284c7"
ACCENT_CYAN_GLOW = "rgba(56, 189, 248, 0.15)"

TESLA_RED = "#e82127"        # Tesla Red for Stop & Critical
HEALTHY = "#10b981"          # Emerald Neon for Connected / Online
WARNING = "#f59e0b"          # Amber
CRITICAL = "#e82127"

# Radii: Precision-engineered, sleek geometric curves
RADIUS_MODAL = 16
RADIUS_CARD = 12
RADIUS_BTN = 8
RADIUS_PILL = 20

# Compatibility Aliases
ACCENT = ACCENT_CYAN
BORDER_SOFT = TESLA_BORDER
PANEL_FILL = TESLA_INPUT
SURFACE_BG = TESLA_BG
SURFACE_CARD = TESLA_CARD
SURFACE_HOVER = TESLA_CARD_HOVER
SURFACE_ACTIVE = TESLA_CARD_ACTIVE
TEXT_1 = TEXT_TITLE
TEXT_2 = TEXT_BODY
TEXT_3 = TEXT_MUTED

FROSTED_BG = TESLA_BG
FROSTED_CARD = TESLA_CARD
FROSTED_CARD_HOVER = TESLA_CARD_HOVER
FROSTED_INPUT = TESLA_INPUT
FROSTED_MODAL = TESLA_MODAL
FROSTED_OVERLAY = TESLA_OVERLAY
FROSTED_BORDER = TESLA_BORDER
SLATE_TITLE = TEXT_TITLE
SLATE_TEXT = TEXT_BODY
SLATE_MUTED = TEXT_MUTED
SLATE_FAINT = TEXT_FAINT
SLATE_BORDER = "rgba(255, 255, 255, 0.18)"
ACCENT_ORANGE = ACCENT_CYAN

MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {TESLA_BG};
    color: {TEXT_BODY};
}}

QWidget {{
    color: {TEXT_BODY};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 5px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.18);
    min-height: 24px;
    border-radius: 2.5px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(56, 189, 248, 0.5);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Cards: Smoked Obsidian Glass */
QFrame#Card {{
    background-color: {TESLA_CARD};
    border: 1px solid {TESLA_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* Primary Buttons: High-Tech Electric Blue */
QPushButton.PrimaryBtn {{
    background-color: {ACCENT_CYAN};
    color: #0b0f17;
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.3px;
}}
QPushButton.PrimaryBtn:hover {{
    background-color: #7dd3fc;
}}
QPushButton.PrimaryBtn:pressed {{
    background-color: {ACCENT_CYAN_HOVER};
}}
QPushButton.PrimaryBtn:disabled {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT_FAINT};
}}

/* Secondary / Frosted Pill Buttons */
QPushButton.PillBtn {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT_TITLE};
    border: 1px solid {TESLA_BORDER};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton.PillBtn:hover {{
    background-color: rgba(255, 255, 255, 0.12);
    border-color: {TESLA_BORDER_HOVER};
}}

/* Danger Buttons (Tesla Red) */
QPushButton.DangerBtn {{
    background-color: rgba(232, 33, 39, 0.12);
    color: {TESLA_RED};
    border: 1px solid rgba(232, 33, 39, 0.4);
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton.DangerBtn:hover {{
    background-color: {TESLA_RED};
    color: #ffffff;
}}

/* Ghost Buttons */
QPushButton.GhostBtn {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 14px;
}}
QPushButton.GhostBtn:hover {{
    color: {TEXT_TITLE};
    background-color: rgba(255, 255, 255, 0.05);
}}

/* Inputs & Form Fields: Precision Smoked Inputs */
QLineEdit, QComboBox {{
    background-color: {TESLA_INPUT};
    color: {TEXT_TITLE};
    border: 1px solid {TESLA_BORDER};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT_CYAN};
    selection-color: #000000;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT_CYAN};
    background-color: rgba(18, 22, 30, 0.95);
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
    background-color: #12151c;
    color: {TEXT_TITLE};
    border: 1px solid {TESLA_BORDER};
    border-radius: 8px;
    selection-background-color: rgba(56, 189, 248, 0.18);
    selection-color: {ACCENT_CYAN};
}}

/* Telemetry Section Header Labels */
QLabel.FormSectionLabel {{
    font-size: 10.5px;
    font-weight: 800;
    color: {TEXT_MUTED};
    letter-spacing: 1.2px;
}}

/* Hairline Separators */
QFrame#Hairline {{
    background-color: {HAIRLINE};
    max-height: 1px;
    border: none;
}}
"""
