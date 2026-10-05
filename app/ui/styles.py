"""Theme definitions and stylesheet matching the Schwalby design system."""

SURFACE_BG = "#121316"
SURFACE_CARD = "#18191f"
SURFACE_HOVER = "#22242b"
SURFACE_ACTIVE = "#2a2d37"
BORDER_SOFT = "#2c2e38"
PANEL_FILL = "#14151a"
PANEL_HAIRLINE = "#23252d"

TEXT_1 = "#f0f1f5"
TEXT_2 = "#b0b3c0"
TEXT_3 = "#727686"

HEALTHY = "#2ec971"
WARNING = "#f5a623"
CRITICAL = "#eb4d4b"
CRITICAL_BRIGHT = "#ff5e57"
ACCENT = "#3b82f6"
ACCENT_BRIGHT = "#60a5fa"

RADIUS_BTN = 6
RADIUS_CARD = 10

MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {SURFACE_BG};
    color: {TEXT_1};
}}

QWidget {{
    color: {TEXT_1};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_SOFT};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_3};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Card Frame */
QFrame#Card {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_CARD}px;
}}

/* Primary Buttons */
QPushButton.PrimaryBtn {{
    background-color: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton.PrimaryBtn:hover {{
    background-color: {ACCENT_BRIGHT};
}}
QPushButton.PrimaryBtn:disabled {{
    background-color: {PANEL_FILL};
    color: {TEXT_3};
}}

/* Secondary Buttons */
QPushButton.SecondaryBtn {{
    background-color: {SURFACE_HOVER};
    color: {TEXT_1};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton.SecondaryBtn:hover {{
    background-color: {SURFACE_ACTIVE};
    border-color: {TEXT_3};
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
    color: {TEXT_2};
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 14px;
}}
QPushButton.GhostBtn:hover {{
    background-color: {SURFACE_HOVER};
    color: {TEXT_1};
}}

/* Inputs and Forms */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {PANEL_FILL};
    color: {TEXT_1};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_BTN}px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit[mono="true"] {{
    font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
    font-size: 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_CARD};
    color: {TEXT_1};
    border: 1px solid {BORDER_SOFT};
    selection-background-color: {SURFACE_HOVER};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: {PANEL_FILL};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {TEXT_1};
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_BRIGHT};
}}

/* Preview Output Block */
QFrame#PreviewBox {{
    background-color: {PANEL_FILL};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_BTN}px;
    padding: 10px 12px;
}}

QLabel.PreviewText {{
    font-family: "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace;
    font-size: 12px;
    color: {TEXT_2};
}}

QLabel.StatusLabel {{
    font-size: 12px;
    color: {TEXT_2};
}}

QDialog {{
    background-color: {SURFACE_BG};
    color: {TEXT_1};
}}
"""
