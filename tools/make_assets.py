"""Regenerate the images in src/ytgrab/assets from code.

    uv run python tools/make_assets.py

The app icon is the mascot on the header's night-sky background, saved as
PNG (Linux, window icon), ICO (Windows shortcut) and ICNS (macOS app bundle).
Nothing here needs a display.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF  # noqa: E402

from ytgrab.mascot import paint_mascot  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "src" / "ytgrab" / "assets"


def canvas(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def icon(size: int) -> QImage:
    """A rounded square in the header's colours with the mascot standing in it."""
    image = canvas(size)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    sky = QLinearGradient(0, 0, size, size)
    sky.setColorAt(0.0, QColor("#121a30"))
    sky.setColorAt(0.55, QColor("#1c3860"))
    sky.setColorAt(1.0, QColor("#23607c"))
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    painter.fillPath(tile, sky)

    figure = size * 0.86
    painter.translate((size - figure) / 2, size * 0.09)
    paint_mascot(painter, figure, "idle")
    painter.end()
    return image


def tick(size: int = 32) -> QImage:
    """The white tick shown inside a ticked checkbox."""
    image = canvas(size)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ffffff"), size * 0.1375)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    unit = size / 32
    painter.drawPolyline(
        QPolygonF([QPointF(7.5 * unit, 16.5 * unit), QPointF(13.5 * unit, 22.5 * unit), QPointF(24.5 * unit, 10 * unit)])
    )
    painter.end()
    return image


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 (Qt needs one to exist before it will paint)
    ASSETS.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon.png": icon(256),
        "icon.ico": icon(256),
        "icon.icns": icon(512),
        "check.png": tick(),
    }
    for name, image in outputs.items():
        target = ASSETS / name
        if not image.save(str(target)):
            raise SystemExit(f"could not write {target}")
        print(f"wrote {target.relative_to(ASSETS.parent.parent.parent)}  ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
