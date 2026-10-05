"""Theme and styling system for Cmdly with Translucent Frosted Glass and Multi-Theme support."""

from typing import Dict, Any
from PySide6.QtCore import QObject, Signal

FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif'
MONO_FONT = '"SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace'

THEMES: Dict[str, Dict[str, Any]] = {
    "tesla_dark": {
        "id": "tesla_dark",
        "name": "Tesla Cyber (Dark Smoked)",
        "bg": "rgba(10, 12, 17, 0.74)",
        "bg_hex": "#0a0c11",
        "card": "rgba(255, 255, 255, 0.05)",
        "card_hover": "rgba(255, 255, 255, 0.10)",
        "card_active": "rgba(56, 189, 248, 0.16)",
        "input": "rgba(14, 17, 24, 0.75)",
        "modal": "rgba(15, 18, 26, 0.94)",
        "overlay": "rgba(4, 5, 8, 0.65)",
        "border": "rgba(255, 255, 255, 0.10)",
        "border_hover": "rgba(255, 255, 255, 0.22)",
        "border_active": "#38bdf8",
        "hairline": "rgba(255, 255, 255, 0.08)",
        "accent": "#38bdf8",
        "accent_hover": "#7dd3fc",
        "accent_glow": "rgba(56, 189, 248, 0.20)",
        "stop": "#e82127",
        "healthy": "#10b981",
        "warning": "#f59e0b",
        "text_title": "#f8fafc",
        "text_body": "#e2e8f0",
        "text_muted": "#94a3b8",
        "text_faint": "#64748b",
        "mac_dark": True,
    },
    "midnight": {
        "id": "midnight",
        "name": "Midnight Obsidian (Deep Indigo)",
        "bg": "rgba(12, 14, 26, 0.76)",
        "bg_hex": "#0c0e1a",
        "card": "rgba(255, 255, 255, 0.06)",
        "card_hover": "rgba(255, 255, 255, 0.12)",
        "card_active": "rgba(129, 140, 248, 0.18)",
        "input": "rgba(18, 21, 38, 0.75)",
        "modal": "rgba(18, 22, 40, 0.94)",
        "overlay": "rgba(5, 6, 14, 0.68)",
        "border": "rgba(255, 255, 255, 0.11)",
        "border_hover": "rgba(255, 255, 255, 0.25)",
        "border_active": "#818cf8",
        "hairline": "rgba(255, 255, 255, 0.08)",
        "accent": "#818cf8",
        "accent_hover": "#a5b4fc",
        "accent_glow": "rgba(129, 140, 248, 0.22)",
        "stop": "#f43f5e",
        "healthy": "#34d399",
        "warning": "#fbbf24",
        "text_title": "#ffffff",
        "text_body": "#e0e7ff",
        "text_muted": "#a5b4fc",
        "text_faint": "#6366f1",
        "mac_dark": True,
    },
    "corvus": {
        "id": "corvus",
        "name": "Corvus Flight Deck (Charcoal)",
        "bg": "rgba(18, 19, 23, 0.80)",
        "bg_hex": "#121317",
        "card": "rgba(255, 255, 255, 0.05)",
        "card_hover": "rgba(255, 255, 255, 0.10)",
        "card_active": "rgba(245, 158, 11, 0.18)",
        "input": "rgba(22, 24, 29, 0.82)",
        "modal": "rgba(24, 26, 32, 0.95)",
        "overlay": "rgba(8, 8, 10, 0.70)",
        "border": "rgba(255, 255, 255, 0.09)",
        "border_hover": "rgba(255, 255, 255, 0.20)",
        "border_active": "#f59e0b",
        "hairline": "rgba(255, 255, 255, 0.07)",
        "accent": "#f59e0b",
        "accent_hover": "#fbbf24",
        "accent_glow": "rgba(245, 158, 11, 0.20)",
        "stop": "#ef4444",
        "healthy": "#10b981",
        "warning": "#f59e0b",
        "text_title": "#f4f4f5",
        "text_body": "#d4d4d8",
        "text_muted": "#a1a1aa",
        "text_faint": "#71717a",
        "mac_dark": True,
    },
    "apple_dark": {
        "id": "apple_dark",
        "name": "Apple Smoked Glass (Vibrant Dark)",
        "bg": "rgba(22, 22, 26, 0.68)",
        "bg_hex": "#16161a",
        "card": "rgba(255, 255, 255, 0.07)",
        "card_hover": "rgba(255, 255, 255, 0.13)",
        "card_active": "rgba(10, 132, 255, 0.18)",
        "input": "rgba(255, 255, 255, 0.08)",
        "modal": "rgba(30, 30, 34, 0.94)",
        "overlay": "rgba(0, 0, 0, 0.60)",
        "border": "rgba(255, 255, 255, 0.12)",
        "border_hover": "rgba(255, 255, 255, 0.24)",
        "border_active": "#0a84ff",
        "hairline": "rgba(255, 255, 255, 0.08)",
        "accent": "#0a84ff",
        "accent_hover": "#409cff",
        "accent_glow": "rgba(10, 132, 255, 0.22)",
        "stop": "#ff453a",
        "healthy": "#30d158",
        "warning": "#ffd60a",
        "text_title": "#ffffff",
        "text_body": "#ebebf5",
        "text_muted": "#a1a1a6",
        "text_faint": "#636366",
        "mac_dark": True,
    },
    "light_frosted": {
        "id": "light_frosted",
        "name": "Light Frosted (Clear Day)",
        "bg": "rgba(245, 246, 250, 0.80)",
        "bg_hex": "#f5f6fa",
        "card": "rgba(255, 255, 255, 0.72)",
        "card_hover": "rgba(255, 255, 255, 0.92)",
        "card_active": "rgba(0, 113, 227, 0.15)",
        "input": "rgba(255, 255, 255, 0.88)",
        "modal": "rgba(255, 255, 255, 0.96)",
        "overlay": "rgba(15, 23, 42, 0.35)",
        "border": "rgba(0, 0, 0, 0.10)",
        "border_hover": "rgba(0, 0, 0, 0.20)",
        "border_active": "#0071e3",
        "hairline": "rgba(0, 0, 0, 0.08)",
        "accent": "#0071e3",
        "accent_hover": "#0077ed",
        "accent_glow": "rgba(0, 113, 227, 0.15)",
        "stop": "#d32f2f",
        "healthy": "#10b981",
        "warning": "#f59e0b",
        "text_title": "#1d1d1f",
        "text_body": "#333336",
        "text_muted": "#6e6e73",
        "text_faint": "#86868b",
        "mac_dark": False,
    },
}

RADIUS_MODAL = 16
RADIUS_CARD = 12
RADIUS_BTN = 9
RADIUS_PILL = 20


class _ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._current_theme_id = "tesla_dark"

    @property
    def current_theme_id(self) -> str:
        return self._current_theme_id

    @property
    def current_theme(self) -> Dict[str, Any]:
        return THEMES.get(self._current_theme_id, THEMES["tesla_dark"])

    def set_theme(self, theme_id: str):
        if theme_id in THEMES and theme_id != self._current_theme_id:
            self._current_theme_id = theme_id
            self._update_constants()
            self.theme_changed.emit(theme_id)

    def _update_constants(self):
        t = self.current_theme
        global TESLA_BG, TESLA_CARD, TESLA_CARD_HOVER, TESLA_INPUT, TESLA_MODAL, TESLA_OVERLAY
        global TESLA_BORDER, TESLA_BORDER_HOVER, TESLA_BORDER_ACTIVE, HAIRLINE
        global TEXT_TITLE, TEXT_BODY, TEXT_MUTED, TEXT_FAINT
        global ACCENT_CYAN, ACCENT_CYAN_HOVER, ACCENT_CYAN_GLOW, TESLA_RED, HEALTHY, WARNING, CRITICAL
        global FROSTED_BG, FROSTED_CARD, FROSTED_CARD_HOVER, FROSTED_INPUT, FROSTED_MODAL, FROSTED_OVERLAY, FROSTED_BORDER
        global SLATE_TITLE, SLATE_TEXT, SLATE_MUTED, SLATE_FAINT, ACCENT, BORDER_SOFT, MAIN_STYLESHEET

        TESLA_BG = t["bg"]
        TESLA_CARD = t["card"]
        TESLA_CARD_HOVER = t["card_hover"]
        TESLA_INPUT = t["input"]
        TESLA_MODAL = t["modal"]
        TESLA_OVERLAY = t["overlay"]
        TESLA_BORDER = t["border"]
        TESLA_BORDER_HOVER = t["border_hover"]
        TESLA_BORDER_ACTIVE = t["border_active"]
        HAIRLINE = t["hairline"]

        TEXT_TITLE = t["text_title"]
        TEXT_BODY = t["text_body"]
        TEXT_MUTED = t["text_muted"]
        TEXT_FAINT = t["text_faint"]

        ACCENT_CYAN = t["accent"]
        ACCENT_CYAN_HOVER = t["accent_hover"]
        ACCENT_CYAN_GLOW = t["accent_glow"]
        TESLA_RED = t["stop"]
        HEALTHY = t["healthy"]
        WARNING = t["warning"]
        CRITICAL = t["stop"]

        ACCENT = ACCENT_CYAN
        BORDER_SOFT = TESLA_BORDER
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

        MAIN_STYLESHEET = self.get_stylesheet()

    def get_stylesheet(self) -> str:
        t = self.current_theme
        bg = t["bg"]
        card = t["card"]
        input_bg = t["input"]
        border = t["border"]
        border_hover = t["border_hover"]
        accent = t["accent"]
        accent_hover = t["accent_hover"]
        stop_col = t["stop"]
        text_title = t["text_title"]
        text_body = t["text_body"]
        text_muted = t["text_muted"]
        text_faint = t["text_faint"]

        return f"""
QMainWindow {{
    background-color: {bg};
    color: {text_body};
}}

QWidget {{
    color: {text_body};
    font-family: {FONT_FAMILY};
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
    background: rgba(255, 255, 255, 0.18);
    min-height: 24px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {accent};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Cards: Frosted Glass */
QFrame#Card {{
    background-color: {card};
    border: 1px solid {border};
    border-radius: {RADIUS_CARD}px;
}}

/* Primary Buttons */
QPushButton.PrimaryBtn {{
    background-color: {accent};
    color: #0b0f17;
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton.PrimaryBtn:hover {{
    background-color: {accent_hover};
}}
QPushButton.PrimaryBtn:disabled {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {text_faint};
}}

/* Pill / Secondary Buttons */
QPushButton.PillBtn {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {text_title};
    border: 1px solid {border};
    border-radius: {RADIUS_BTN}px;
    padding: 7px 15px;
    font-weight: 500;
    font-size: 12.5px;
}}
QPushButton.PillBtn:hover {{
    background-color: rgba(255, 255, 255, 0.12);
    border-color: {border_hover};
}}

/* Danger Buttons */
QPushButton.DangerBtn {{
    background-color: rgba(232, 33, 39, 0.14);
    color: {stop_col};
    border: 1px solid rgba(232, 33, 39, 0.4);
    border-radius: {RADIUS_BTN}px;
    padding: 7px 15px;
    font-weight: 600;
}}
QPushButton.DangerBtn:hover {{
    background-color: {stop_col};
    color: #ffffff;
}}

/* Ghost Buttons */
QPushButton.GhostBtn {{
    background-color: transparent;
    color: {text_muted};
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 6px 12px;
}}
QPushButton.GhostBtn:hover {{
    color: {text_title};
    background-color: rgba(255, 255, 255, 0.08);
}}

/* Inputs & Form Fields */
QLineEdit, QComboBox {{
    background-color: {input_bg};
    color: {text_title};
    border: 1px solid {border};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {accent};
    selection-color: #000000;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {accent};
    background-color: rgba(255, 255, 255, 0.10);
}}
QLineEdit[mono="true"] {{
    font-family: {MONO_FONT};
    font-size: 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: #161822;
    color: {text_title};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent};
    selection-color: #000000;
}}

QLabel.FormSectionLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {text_muted};
    letter-spacing: 0.5px;
}}

QFrame#Hairline {{
    background-color: {t["hairline"]};
    max-height: 1px;
    border: none;
}}
"""


theme_manager = _ThemeManager()

# Export default active variables
_init_t = theme_manager.current_theme
TESLA_BG = _init_t["bg"]
TESLA_CARD = _init_t["card"]
TESLA_CARD_HOVER = _init_t["card_hover"]
TESLA_INPUT = _init_t["input"]
TESLA_MODAL = _init_t["modal"]
TESLA_OVERLAY = _init_t["overlay"]
TESLA_BORDER = _init_t["border"]
TESLA_BORDER_HOVER = _init_t["border_hover"]
TESLA_BORDER_ACTIVE = _init_t["border_active"]
HAIRLINE = _init_t["hairline"]

TEXT_TITLE = _init_t["text_title"]
TEXT_BODY = _init_t["text_body"]
TEXT_MUTED = _init_t["text_muted"]
TEXT_FAINT = _init_t["text_faint"]

ACCENT_CYAN = _init_t["accent"]
ACCENT_CYAN_HOVER = _init_t["accent_hover"]
ACCENT_CYAN_GLOW = _init_t["accent_glow"]
TESLA_RED = _init_t["stop"]
HEALTHY = _init_t["healthy"]
WARNING = _init_t["warning"]
CRITICAL = _init_t["stop"]

ACCENT = ACCENT_CYAN
BORDER_SOFT = TESLA_BORDER
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

PANEL_FILL = TESLA_INPUT
SURFACE_BG = TESLA_BG
SURFACE_CARD = TESLA_CARD
SURFACE_HOVER = TESLA_CARD_HOVER
SURFACE_ACTIVE = TESLA_CARD_HOVER
TEXT_1 = TEXT_TITLE
TEXT_2 = TEXT_BODY
TEXT_3 = TEXT_MUTED

MAIN_STYLESHEET = theme_manager.get_stylesheet()
