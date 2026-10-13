"""The colour themes: four palettes, the Qt palette and stylesheet built from them.

A theme is a dozen hand-picked colours; hovers, hairlines, disabled tones and
the like are mixed from those, so a new theme is one short entry in THEMES.
Custom-painted widgets read `current()` each time they paint, which is what
lets the theme change while the app runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, Qt, QTemporaryDir
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent / "assets"
ICON_PATH = ASSETS / "icon.png"

# One scale of sizes for everything that is drawn, so no corner or control is a one-off.
RADIUS_PANEL = 14
RADIUS_CONTROL = 8
RADIUS_SMALL = 5
CONTROL_HEIGHT = 40  # text fields, dropdowns and buttons
COMPACT_HEIGHT = 32  # the same, inside a table row or beside a heading


# ------------------------------------------------------------ colour mixing


def _channels(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix(first: str, second: str, amount: float) -> str:
    """`first` moved `amount` (0..1) of the way towards `second`."""
    a, b = _channels(first), _channels(second)
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def lighten(color: str, amount: float) -> str:
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float) -> str:
    return mix(color, "#000000", amount)


# -------------------------------------------------------------------- themes


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    dark: bool
    base: str  # the window behind everything
    surface: str  # panels
    field: str  # text fields, tracks, dropdowns
    ink: str  # text
    muted: str  # secondary text
    line: str  # quiet borders
    accent: str  # the main action, and progress
    on_accent: str  # text on top of the accent
    gold: str  # ornaments: rings, rules, numerals
    jewel: str  # the one contrasting colour: bow tie, playlist badge
    band: str  # the header band, always a deep colour

    # --- tones mixed from the above

    @property
    def accent_hover(self) -> str:
        return lighten(self.accent, 0.14) if self.dark else lighten(self.accent, 0.10)

    @property
    def accent_down(self) -> str:
        return darken(self.accent, 0.14)

    @property
    def hairline(self) -> str:
        return mix(self.surface, self.gold, 0.24)

    @property
    def hairline_strong(self) -> str:
        return mix(self.surface, self.gold, 0.55)

    @property
    def ornament(self) -> str:
        """Gold turned down, for rings and numerals: decoration must not compete with the buttons."""
        return mix(self.surface, self.gold, 0.6)

    @property
    def heading(self) -> str:
        """Small capitals that name a column or a control."""
        return mix(self.muted, self.gold, 0.3)

    @property
    def disabled(self) -> str:
        return mix(self.muted, self.surface, 0.48)

    @property
    def select(self) -> str:
        return mix(self.surface, self.accent, 0.26)

    @property
    def done(self) -> str:
        return "#8fb79a" if self.dark else "#2f6b4d"

    @property
    def failed(self) -> str:
        return "#e09a92" if self.dark else "#a3352b"

    @property
    def band_gold(self) -> str:
        """Gold that reads on the header band: the light theme's own gold is too deep for it."""
        return self.gold if self.dark else lighten(self.gold, 0.38)

    @property
    def shadow(self) -> int:
        """Opacity (0..255) of the soft shadow under a panel."""
        return 120 if self.dark else 46

    def tokens(self) -> dict[str, str]:
        """Every colour the stylesheet uses, by name."""
        return {
            "base": self.base,
            "surface": self.surface,
            "field": self.field,
            "ink": self.ink,
            "muted": self.muted,
            "line": self.line,
            "accent": self.accent,
            "on_accent": self.on_accent,
            "gold": self.gold,
            "hairline": self.hairline,
            "hairline_strong": self.hairline_strong,
            "disabled": self.disabled,
            "select": self.select,
            "scroll": mix(self.surface, self.gold, 0.32),
            "scroll_hover": mix(self.surface, self.gold, 0.6),
            "button": mix(self.surface, self.ink, 0.06),
            "button_hover": mix(self.surface, self.ink, 0.12),
            "heading": self.heading,
            "radius": str(RADIUS_CONTROL),
            "radius_small": str(RADIUS_SMALL),
        }


THEMES: dict[str, Theme] = {
    theme.key: theme
    for theme in (
        Theme(
            key="heritage", name="Heritage green", dark=True,
            base="#0b1813", surface="#11231c", field="#0a1611", ink="#efe7d6", muted="#a1a594", line="#273b31",
            accent="#c9a961", on_accent="#1a1408", gold="#c9a961", jewel="#8a3443", band="#0d2019",
        ),
        Theme(
            key="midnight", name="Midnight navy", dark=True,
            base="#0a111e", surface="#101a2d", field="#090f1a", ink="#ece6d8", muted="#9ba2b1", line="#25314b",
            accent="#cdae6b", on_accent="#181308", gold="#cdae6b", jewel="#8a3443", band="#0c1628",
        ),
        Theme(
            key="bordeaux", name="Bordeaux", dark=True,
            base="#160b0e", surface="#211217", field="#13080b", ink="#f0e6da", muted="#b49f9c", line="#3e232a",
            accent="#cfae6c", on_accent="#1a1208", gold="#cfae6c", jewel="#3b7a62", band="#1e0d12",
        ),
        Theme(
            key="ivory", name="Ivory", dark=False,
            base="#ece4d2", surface="#f9f5ea", field="#fffdf7", ink="#26211a", muted="#75695a", line="#d5c9b0",
            accent="#1d4838", on_accent="#f7f0e1", gold="#9a7a32", jewel="#8a3443", band="#143528",
        ),
    )
}  # fmt: skip

DEFAULT_DARK = "heritage"
DEFAULT_LIGHT = "ivory"
AUTO = "auto"

_current: Theme = THEMES[DEFAULT_DARK]


def current() -> Theme:
    """The theme now showing."""
    return _current


def select(key: str) -> Theme:
    """Make a theme current without styling an application; for drawing off screen."""
    global _current
    _current = THEMES[key]
    return _current


def is_dark(app: QApplication) -> bool:
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def resolve(app: QApplication, saved: str | None = None) -> Theme:
    """Pick the theme: YTGRAB_THEME for this run, else the saved choice, else one that suits the system."""
    forced = os.environ.get("YTGRAB_THEME", "").strip().lower()
    forced = {"dark": DEFAULT_DARK, "light": DEFAULT_LIGHT}.get(forced, forced)
    for choice in (forced, (saved or "").strip().lower()):
        if choice in THEMES:
            return THEMES[choice]
    return THEMES[DEFAULT_DARK if is_dark(app) else DEFAULT_LIGHT]


# ------------------------------------------------- small images for controls

# Stylesheets can only show a tick or an arrow from an image file, and the right
# colour depends on the theme, so they are drawn on demand into a temporary folder.
_image_dir: QTemporaryDir | None = None


def _draw(path: str, size: int, color: str, points: list[tuple[float, float]], width: float) -> str:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(QPolygonF([QPointF(x * size, y * size) for x, y in points]))
    painter.end()
    image.save(path)
    return path


def _control_images(theme: Theme) -> dict[str, str]:
    global _image_dir
    if _image_dir is None:
        _image_dir = QTemporaryDir()
    folder = Path(_image_dir.path())
    tick = [(0.23, 0.52), (0.42, 0.70), (0.77, 0.31)]
    chevron = [(0.22, 0.38), (0.50, 0.66), (0.78, 0.38)]
    return {
        "tick": _draw((folder / f"tick-{theme.key}.png").as_posix(), 32, theme.on_accent, tick, 4.4),
        "chevron": _draw((folder / f"chevron-{theme.key}.png").as_posix(), 24, theme.gold, chevron, 2.6),
        "chevron_off": _draw((folder / f"chevron-off-{theme.key}.png").as_posix(), 24, theme.disabled, chevron, 2.6),
    }


# ---------------------------------------------------------------- stylesheet

# Buttons, progress bars, panels and headings paint themselves (see widgets.py).
# This covers the standard controls that are left.
STYLE = Template("""
QToolTip {
    background: $surface; color: $ink; border: 1px solid $hairline_strong; border-radius: ${radius_small}px;
    padding: 6px 9px;
}

QLineEdit {
    background: $field; color: $ink; border: 1px solid $line; border-radius: ${radius}px; padding: 8px 12px;
    selection-background-color: $accent; selection-color: $on_accent;
}
QLineEdit:hover { border-color: $hairline_strong; }
QLineEdit:focus { border-color: $gold; }
QLineEdit:disabled { color: $disabled; }

QComboBox {
    background: $field; color: $ink; border: 1px solid $line; border-radius: ${radius}px;
    padding: 5px 6px 5px 12px; min-height: 20px;
}
QComboBox:hover { border-color: $hairline_strong; }
QComboBox:focus { border-color: $gold; }
QComboBox:disabled { color: $disabled; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 30px; border: none; }
QComboBox::down-arrow { image: url("$chevron"); width: 11px; height: 11px; }
QComboBox::down-arrow:disabled { image: url("$chevron_off"); }
QComboBox QAbstractItemView {
    background: $surface; color: $ink; border: 1px solid $hairline_strong; outline: none; padding: 4px;
}
QComboBox QAbstractItemView::item { padding: 7px 10px; border-radius: ${radius_small}px; color: $ink; }
QComboBox QAbstractItemView::item:selected { background: $select; color: $ink; }

QCheckBox { color: $ink; spacing: 10px; }
QCheckBox:disabled { color: $disabled; }
QCheckBox::indicator, QTableView::indicator {
    width: 17px; height: 17px; border: 1px solid $hairline_strong; border-radius: ${radius_small}px;
    background: $field;
}
QCheckBox::indicator:hover, QTableView::indicator:hover, QCheckBox::indicator:focus { border-color: $gold; }
QCheckBox::indicator:checked, QTableView::indicator:checked {
    background: $accent; border-color: $accent; image: url("$tick");
}
QCheckBox::indicator:disabled, QTableView::indicator:disabled { border-color: $line; }
QCheckBox::indicator:checked:disabled, QTableView::indicator:checked:disabled {
    background: $disabled; border-color: $disabled;
}

QTableWidget { background: transparent; color: $ink; border: none; }
QHeaderView { background: transparent; }
QHeaderView::section {
    background: transparent; color: $heading; border: none; border-bottom: 1px solid $hairline; padding: 10px 6px;
}
QTableCornerButton::section { background: transparent; border: none; }

QPlainTextEdit {
    background: $field; color: $ink; border: 1px solid $line; border-radius: ${radius}px; padding: 6px;
    selection-background-color: $accent; selection-color: $on_accent;
}

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: $scroll; border-radius: 3px; }
QScrollBar::handle:vertical { min-height: 36px; }
QScrollBar::handle:horizontal { min-width: 36px; }
QScrollBar::handle:hover { background: $scroll_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: $surface; color: $ink; border: 1px solid $hairline_strong; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: ${radius_small}px; }
QMenu::item:selected { background: $select; }
QMenu::item:disabled { color: $disabled; }

QMessageBox, QFileDialog, QDialog { background: $surface; }
QPushButton {
    background: $button; color: $ink; border: 1px solid $hairline_strong; border-radius: ${radius}px; padding: 8px 18px;
}
QPushButton:hover { background: $button_hover; border-color: $gold; }
QPushButton:disabled { color: $disabled; border-color: $line; }
""")


def _palette(theme: Theme) -> QPalette:
    """Feeds whatever Qt still draws by itself, and the text colours of plain labels."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: theme.base,
        QPalette.ColorRole.WindowText: theme.ink,
        QPalette.ColorRole.Base: theme.field,
        QPalette.ColorRole.AlternateBase: mix(theme.surface, theme.ink, 0.03),
        QPalette.ColorRole.Text: theme.ink,
        QPalette.ColorRole.Button: mix(theme.surface, theme.ink, 0.06),
        QPalette.ColorRole.ButtonText: theme.ink,
        QPalette.ColorRole.ToolTipBase: theme.surface,
        QPalette.ColorRole.ToolTipText: theme.ink,
        QPalette.ColorRole.PlaceholderText: mix(theme.muted, theme.field, 0.25),
        QPalette.ColorRole.Highlight: theme.accent,
        QPalette.ColorRole.HighlightedText: theme.on_accent,
        QPalette.ColorRole.Link: theme.gold,
        QPalette.ColorRole.Mid: theme.line,
        QPalette.ColorRole.Light: lighten(theme.surface, 0.10),
        QPalette.ColorRole.Midlight: theme.surface,
        QPalette.ColorRole.Dark: darken(theme.line, 0.25),
        QPalette.ColorRole.Shadow: darken(theme.line, 0.5),
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(theme.disabled))
    return palette


def apply(app: QApplication, saved: str | None = None) -> Theme:
    """Dress the whole app in the theme `resolve` picks; returns it."""
    global _current
    _current = resolve(app, saved)
    app.setStyle("Fusion")
    app.setPalette(_palette(_current))
    app.setStyleSheet(STYLE.substitute({**_current.tokens(), **_control_images(_current)}))
    return _current
