"""Colours, palette and stylesheet, in a light and a dark flavour that follow the system."""

from __future__ import annotations

import os
from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent / "assets"
ICON_PATH = ASSETS / "icon.png"
CHECK_PATH = ASSETS / "check.png"

LIGHT = {
    "window": "#eef1f6",
    "card": "#ffffff",
    "field": "#ffffff",
    "border": "#d5dbe6",
    "text": "#1b2230",
    "muted": "#5f6b7e",
    "disabled": "#a3acba",
    "button": "#ffffff",
    "button_hover": "#eaeff7",
    "accent": "#2c5fd6",
    "accent_hover": "#2450ba",
    "accent_text": "#ffffff",
    "chunk": "#a8c2f7",
    "done": "#a5dcb8",
    "failed": "#c0392b",
    "alt_row": "#f6f8fc",
    "header_row": "#eef1f6",
}

DARK = {
    "window": "#12151a",
    "card": "#1a1e26",
    "field": "#11141a",
    "border": "#2b323d",
    "text": "#e7eaf0",
    "muted": "#98a2b3",
    "disabled": "#5b6472",
    "button": "#252b36",
    "button_hover": "#303847",
    "accent": "#3d6bd6",
    "accent_hover": "#4c7be8",
    "accent_text": "#ffffff",
    "chunk": "#3458ad",
    "done": "#2c7448",
    "failed": "#ff8a80",
    "alt_row": "#1e232c",
    "header_row": "#222834",
}

# The header keeps its own night-sky colours in both flavours, so it is not tokenised.
STYLE = Template("""
QFrame#header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121a30, stop:0.55 #1c3860, stop:1 #23607c);
}
QLabel#appTitle { color: #ffffff; font-size: 22px; font-weight: 700; }
QLabel#appTagline { color: #c4d3ea; font-size: 13px; }

QFrame#card { background: $card; border: 1px solid $border; border-radius: 12px; }
QLabel#stepNumber {
    background: $accent; color: $accent_text; border-radius: 13px; font-size: 13px; font-weight: 700;
}
QLabel#stepTitle { color: $text; font-size: 16px; font-weight: 700; }
QLabel#stepHint, QLabel#muted { color: $muted; font-size: 12px; }
QLabel#optionLabel { color: $muted; }

QFrame#footer { background: $card; border-top: 1px solid $border; }
QFrame#footer QLabel { color: $muted; font-size: 12px; }

QLineEdit {
    background: $field; color: $text; border: 1px solid $border; border-radius: 8px; padding: 7px 10px;
    selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit:focus { border-color: $accent; }
QLineEdit:disabled { color: $disabled; }

QPushButton {
    background: $button; color: $text; border: 1px solid $border; border-radius: 8px; padding: 7px 16px;
}
QPushButton:hover { background: $button_hover; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $disabled; }
QPushButton[primary="true"] {
    background: $accent; color: $accent_text; border-color: $accent; font-weight: 600; padding: 7px 20px;
}
QPushButton[primary="true"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[primary="true"]:disabled { background: $border; border-color: $border; color: $disabled; }

QToolButton {
    background: transparent; color: $muted; border: 1px solid transparent; border-radius: 8px; padding: 5px 9px;
}
QToolButton:hover, QToolButton:checked { background: $button_hover; color: $text; border-color: $border; }

QCheckBox { color: $text; spacing: 8px; }
QCheckBox:disabled { color: $disabled; }
QCheckBox::indicator, QTableView::indicator {
    width: 16px; height: 16px; border: 1px solid $muted; border-radius: 4px; background: $field;
}
QCheckBox::indicator:checked, QTableView::indicator:checked {
    background: $accent; border-color: $accent; image: url("$check");
}
QCheckBox::indicator:disabled, QTableView::indicator:disabled { border-color: $disabled; }
QCheckBox::indicator:checked:disabled, QTableView::indicator:checked:disabled {
    background: $disabled; border-color: $disabled;
}

QTableWidget { background: $card; alternate-background-color: $alt_row; color: $text; border: none; }
QHeaderView::section {
    background: $header_row; color: $muted; border: none; border-bottom: 1px solid $border;
    padding: 8px 10px; font-weight: 600;
}

QProgressBar {
    background: $field; color: $text; border: 1px solid $border; border-radius: 8px;
    text-align: center; min-height: 20px;
}
QProgressBar::chunk { background: $chunk; border-radius: 7px; }
QProgressBar[state="done"]::chunk { background: $done; }
QProgressBar[state="failed"] { color: $failed; }
QProgressBar#overall { min-height: 10px; max-height: 10px; border-radius: 6px; }
QProgressBar#overall::chunk { background: $accent; border-radius: 5px; }

QPlainTextEdit {
    background: $field; color: $text; border: 1px solid $border; border-radius: 8px;
    font-size: 12px;
}
QScrollArea, QWidget#linkRows { background: transparent; }
QToolTip { background: $card; color: $text; border: 1px solid $border; padding: 4px 6px; }
""")


def is_dark(app: QApplication) -> bool:
    forced = os.environ.get("YTGRAB_THEME", "").lower()  # for trying the other flavour
    if forced in ("dark", "light"):
        return forced == "dark"
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def _palette(colors: dict[str, str]) -> QPalette:
    """Feeds the widgets Fusion draws itself: dropdowns, the spin box, checkboxes, scroll bars."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "window",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "field",
        QPalette.ColorRole.AlternateBase: "alt_row",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "button",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.ToolTipBase: "card",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.HighlightedText: "accent_text",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.Mid: "border",
    }
    for role, name in roles.items():
        palette.setColor(role, QColor(colors[name]))
    # Bevel shades Fusion uses for its own controls, derived so both flavours stay consistent.
    palette.setColor(QPalette.ColorRole.Light, QColor(colors["card"]).lighter(112))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(colors["card"]))
    palette.setColor(QPalette.ColorRole.Dark, QColor(colors["border"]).darker(130))
    palette.setColor(QPalette.ColorRole.Shadow, QColor(colors["border"]).darker(170))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled"]))
    return palette


def apply(app: QApplication) -> dict[str, str]:
    """Style the whole app for the current colour scheme; returns the colours in use."""
    colors = DARK if is_dark(app) else LIGHT
    app.setStyle("Fusion")
    app.setPalette(_palette(colors))
    app.setStyleSheet(STYLE.substitute(colors, check=CHECK_PATH.as_posix()))
    return colors
