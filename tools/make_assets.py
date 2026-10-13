"""Regenerate the app icon in src/ytgrab/assets from code.

    uv run python tools/make_assets.py

The icon is the mascot on a deep green tile with a gold frame, in the Heritage
theme's colours. It is saved as PNG (Linux, window icon), ICO (Windows
shortcut) and ICNS (macOS app bundle). Nothing here needs a display.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402

from ytgrab import theme  # noqa: E402
from ytgrab.mascot import paint_mascot  # noqa: E402
from ytgrab.theme import darken, mix  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "src" / "ytgrab" / "assets"


def icon(size: int) -> QImage:
    """A rounded tile in the header's colours, framed in gold, with the mascot standing in it."""
    current = theme.select("heritage")
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    felt = QLinearGradient(0, 0, size, size)
    felt.setColorAt(0.0, QColor(darken(current.band, 0.35)))
    felt.setColorAt(0.55, QColor(current.band))
    felt.setColorAt(1.0, QColor(mix(current.band, current.gold, 0.22)))
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    painter.fillPath(tile, felt)

    inset = size * 0.055
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(current.gold), max(1.0, size * 0.012)))
    painter.drawRoundedRect(QRectF(inset, inset, size - inset * 2, size - inset * 2), size * 0.17, size * 0.17)

    figure = size * 0.8
    painter.translate((size - figure) / 2, size * 0.115)
    paint_mascot(painter, figure, "idle")
    painter.end()
    return image


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 (Qt needs one to exist before it will paint)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon.png", 256), ("icon.ico", 256), ("icon.icns", 512)):
        target = ASSETS / name
        if not icon(size).save(str(target)):
            raise SystemExit(f"could not write {target}")
        print(f"wrote {target.relative_to(ASSETS.parent.parent.parent)}  ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
