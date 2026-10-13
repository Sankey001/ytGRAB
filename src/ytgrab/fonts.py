"""The two bundled typefaces and the fonts built from them.

Cinzel (inscription capitals) carries the wordmark and section titles;
Playfair Display the tagline, hints and large figures. Both ship under the
SIL Open Font License, whose text sits beside them in assets/fonts.

Both are variable fonts, and their weight has to be set through the 'wght'
axis: asking Qt for a bold weight the usual way (QFont.setWeight, or
font-weight in a stylesheet) leaves the light letterforms in place and smears
them. So every font here is built in code, never by the stylesheet.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
DISPLAY = "Cinzel"
SERIF = "Playfair Display"
SERIF_FALLBACKS = ["Georgia", "Palatino Linotype", "Baskerville", "Noto Serif", "DejaVu Serif", "serif"]

_loaded = False


def load() -> None:
    """Register the bundled fonts with Qt. Safe to call more than once; needs a QApplication."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    for file in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(file))


def _variable(family: str, pixels: float, weight: int, tracking: float) -> QFont:
    load()
    font = QFont()
    font.setFamilies([family, *SERIF_FALLBACKS])  # if a file is missing, a system serif steps in
    font.setPixelSize(round(pixels))
    if hasattr(font, "setVariableAxis"):  # Qt 6.7 and later
        font.setVariableAxis(QFont.Tag("wght"), float(weight))
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    return font


def display(pixels: float, weight: int = 500, tracking: float = 0.0) -> QFont:
    """Cinzel: capitals only, for the wordmark, section titles and numerals in medallions."""
    return _variable(DISPLAY, pixels, weight, tracking)


def serif(pixels: float, weight: int = 400, italic: bool = False, lining: bool = False) -> QFont:
    """Playfair Display. `lining` swaps its old-style figures for ones that sit on the line, for readouts."""
    font = _variable(SERIF, pixels, weight, 0.0)
    font.setItalic(italic)
    if lining and hasattr(font, "setFeature"):
        font.setFeature(QFont.Tag("lnum"), 1)
    return font


def sans(
    pixels: float,
    weight: QFont.Weight = QFont.Weight.Normal,
    tracking: float = 0.0,
    caps: bool = False,
    tabular: bool = False,
) -> QFont:
    """The system's own interface font, for everything that is data rather than ornament.

    `tabular` asks for figures of equal width, so the numbers in a column line up.
    """
    font = QFont(QApplication.font())
    font.setPixelSize(round(pixels))
    font.setWeight(weight)
    if tabular and hasattr(font, "setFeature"):  # Qt 6.7 and later
        font.setFeature(QFont.Tag("tnum"), 1)
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    if caps:
        font.setCapitalization(QFont.Capitalization.AllUppercase)
    return font
