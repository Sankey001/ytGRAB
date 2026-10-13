"""The header's figurine: an original TV-headed butler, drawn in code, that reacts to what the app is doing.

`paint_mascot` does the drawing and needs only a QPainter, so the same figure
serves the widget in the header and the app icon. Its colours come from the
current theme.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from ytgrab import fonts, motion, theme
from ytgrab.theme import darken, lighten

MOODS = ("idle", "busy", "happy", "sad")

IVORY = QColor("#f6efdd")
SHADE = QColor("#d9ccab")
GOOD = QColor("#a9dcb6")
BAD = QColor("#ec9f97")
BLUSH = QColor(236, 150, 160, 150)

# Where the hands sit for each mood, in the 120 x 120 drawing space.
HANDS = {
    "idle": ((27, 93), (93, 93)),
    "busy": ((17, 80), (103, 80)),
    "happy": ((12, 66), (108, 66)),
    "sad": ((31, 99), (89, 99)),
}
ANTENNA_TIPS = {"sad": ((33, 12), (87, 12))}  # droop when sad
ANTENNA_UP = ((38, 7), (82, 7))


def _colors(on_band: bool) -> dict[str, QColor]:
    current = theme.current()
    return {
        "outline": QColor(darken(current.band, 0.55)),
        "screen": QColor(darken(current.band, 0.35)),
        "glow": QColor(lighten(current.band_gold, 0.3)),  # eyes and the busy arrow, on the dark screen
        # antenna tips: the light theme's deep gold would vanish on the band, its pale gold on a page
        "gold": QColor(current.band_gold if on_band else current.gold),
        "mark": QColor(current.band_gold),  # the play mark, on the dark chest display
        "bow": QColor(current.jewel),
        "knot": QColor(darken(current.jewel, 0.3)),
    }


def paint_mascot(
    painter: QPainter, size: float, mood: str = "idle", phase: float = 0.0, blink: bool = False, on_band: bool = True
) -> None:
    """Draw the mascot into a `size` x `size` square at the painter's origin.

    `phase` runs 0..1 and drives the busy animation; `blink` closes the eyes.
    `on_band` says whether it stands on the deep header band or on the page.
    """
    colors = _colors(on_band)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 120, size / 120)

    bob = math.sin(phase * 2 * math.pi) * 1.6 if mood == "busy" else 0.0
    outline = QPen(colors["outline"], 2.4)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    # The shadow stays on the ground while the body bobs above it.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 80))
    painter.drawEllipse(QPointF(60, 112), 27 - bob, 4.5)
    painter.translate(0, bob)

    _limbs(painter, mood, outline)
    painter.setPen(outline)
    painter.setBrush(IVORY)
    painter.drawRoundedRect(QRectF(37, 66, 46, 36), 11, 11)  # torso
    _chest_light(painter, colors, mood, phase)
    _head(painter, colors, mood, phase, outline)
    _bow_tie(painter, colors)
    _face(painter, colors, mood, blink)
    painter.restore()


def _limbs(painter: QPainter, mood: str, outline: QPen) -> None:
    arm = QPen(SHADE, 7)
    arm.setCapStyle(Qt.PenCapStyle.RoundCap)
    left, right = HANDS[mood]
    painter.setPen(arm)
    painter.drawLine(QPointF(40, 80), QPointF(*left))
    painter.drawLine(QPointF(80, 80), QPointF(*right))
    painter.setPen(outline)
    painter.setBrush(IVORY)  # white gloves
    for hand in (left, right):
        painter.drawEllipse(QPointF(*hand), 4.6, 4.6)
    painter.setBrush(SHADE)
    painter.drawRoundedRect(QRectF(41, 99, 15, 10), 4.5, 4.5)  # feet
    painter.drawRoundedRect(QRectF(64, 99, 15, 10), 4.5, 4.5)


def _chest_light(painter: QPainter, colors: dict, mood: str, phase: float) -> None:
    """A round display on the chest: play when idle, a falling arrow when busy, a tick or '!' after."""
    centre = QPointF(60, 88)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colors["screen"])
    painter.drawEllipse(centre, 9.5, 9.5)

    painter.save()
    clip = QPainterPath()
    clip.addEllipse(centre, 8.5, 8.5)
    painter.setClipPath(clip)
    if mood == "idle":
        painter.setBrush(colors["mark"])
        painter.drawPolygon(QPolygonF([QPointF(57.2, 83.4), QPointF(57.2, 92.6), QPointF(65.4, 88)]))
    else:
        pen = QPen({"busy": colors["glow"], "happy": GOOD, "sad": BAD}[mood], 2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if mood == "busy":
            drop = (phase * 2 % 1.0) * 28 - 14  # falls through the display twice per cycle
            painter.drawLine(QPointF(60, 82 + drop), QPointF(60, 93 + drop))
            painter.drawPolyline(
                QPolygonF([QPointF(55.5, 88.5 + drop), QPointF(60, 93 + drop), QPointF(64.5, 88.5 + drop)])
            )
        elif mood == "happy":
            painter.drawPolyline(QPolygonF([QPointF(54.5, 88), QPointF(58.5, 92), QPointF(65.5, 84)]))
        else:
            painter.drawLine(QPointF(60, 82.5), QPointF(60, 89.5))
            painter.drawPoint(QPointF(60, 93.5))
    painter.restore()


def _head(painter: QPainter, colors: dict, mood: str, phase: float, outline: QPen) -> None:
    tips = ANTENNA_TIPS.get(mood, ANTENNA_UP)
    rod = QPen(IVORY, 3)
    rod.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(rod)
    painter.drawLine(QPointF(50, 22), QPointF(*tips[0]))
    painter.drawLine(QPointF(70, 22), QPointF(*tips[1]))

    gold, glow = colors["gold"], colors["glow"]
    tip_colors = {
        "idle": (gold, gold),
        "busy": (glow, gold) if phase < 0.5 else (gold, glow),  # they take turns lighting up
        "happy": (GOOD, GOOD),
        "sad": (SHADE, SHADE),
    }[mood]
    painter.setPen(QPen(colors["outline"], 1.2))
    for tip, color in zip(tips, tip_colors):
        painter.setBrush(color)
        painter.drawEllipse(QPointF(*tip), 4.2, 4.2)

    painter.setPen(outline)
    painter.setBrush(IVORY)
    painter.drawRoundedRect(QRectF(22, 20, 76, 48), 14, 14)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colors["screen"])
    painter.drawRoundedRect(QRectF(30, 27, 60, 34), 9, 9)


def _bow_tie(painter: QPainter, colors: dict) -> None:
    painter.setPen(QPen(colors["knot"], 1.1))
    painter.setBrush(colors["bow"])
    for side in (-1, 1):
        painter.drawPolygon(
            QPolygonF([QPointF(60, 71), QPointF(60 + side * 10.5, 65.2), QPointF(60 + side * 10.5, 76.8)])
        )
    painter.setBrush(colors["knot"])
    painter.drawRoundedRect(QRectF(57.3, 68.2, 5.4, 5.6), 1.8, 1.8)


def _face(painter: QPainter, colors: dict, mood: str, blink: bool) -> None:
    glow = colors["glow"]
    line = QPen(glow, 2.4)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)

    def curve(start: tuple, bend: tuple, end: tuple) -> QPainterPath:
        path = QPainterPath(QPointF(*start))
        path.quadTo(QPointF(*bend), QPointF(*end))
        return path

    def stroke() -> None:
        painter.setPen(line)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def eyes(y: float, rx: float, ry: float) -> None:
        if blink:
            stroke()
            for x in (48, 72):
                painter.drawLine(QPointF(x - rx, y + 1), QPointF(x + rx, y + 1))
            return
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (48, 72):
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(x, y), rx, ry)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(x + 1.6, y - ry * 0.4), 1.3, 1.3)

    if mood == "idle":
        eyes(42, 4.4, 6.0)
        stroke()
        painter.drawPath(curve((53, 51.5), (60, 56.5), (67, 51.5)))
    elif mood == "busy":  # looking down at the chest light
        eyes(45, 4.5, 4.5)
        stroke()
        painter.drawEllipse(QPointF(60, 54.5), 2.4, 2.4)
    elif mood == "happy":
        stroke()
        painter.drawPath(curve((43, 45), (48, 36.5), (53, 45)))
        painter.drawPath(curve((67, 45), (72, 36.5), (77, 45)))
        smile = curve((52, 49.5), (60, 59.5), (68, 49.5))
        smile.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawPath(smile)
        painter.setBrush(BLUSH)
        painter.drawEllipse(QPointF(38, 52), 4, 2.6)
        painter.drawEllipse(QPointF(82, 52), 4, 2.6)
    else:  # sad
        eyes(45, 3.6, 4.2)
        stroke()
        painter.drawLine(QPointF(43, 38.5), QPointF(52, 35.5))  # brows raised in the middle: worried
        painter.drawLine(QPointF(77, 38.5), QPointF(68, 35.5))
        painter.drawPath(curve((54, 56.5), (60, 51.5), (66, 56.5)))


class Mascot(QWidget):
    """The figurine as a widget. Moods: idle (blinks now and then), busy (animated), happy, sad."""

    def __init__(self, size: int = 88, on_band: bool = True) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.on_band = on_band
        self._mood = "idle"
        self._phase = 0.0  # 0..1, only advances while busy
        self._blinking = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._step)
        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._on_blink)

    def mood(self) -> str:
        return self._mood

    def set_mood(self, mood: str) -> None:
        if mood == self._mood or mood not in MOODS:
            return
        self._mood = mood
        self._phase = 0.0
        self._blinking = False
        if mood == "busy" and motion.enabled():
            self._timer.start()
        else:
            self._timer.stop()
        self._plan_blink()
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._plan_blink()
        super().showEvent(event)

    def _plan_blink(self) -> None:
        if self._mood == "idle" and motion.enabled():
            self._blink_timer.start(random.randint(2600, 5600))
        else:
            self._blink_timer.stop()

    def _on_blink(self) -> None:
        self._blinking = not self._blinking
        self.update()
        if self._blinking:
            self._blink_timer.start(140)  # eyes stay shut this long
        else:
            self._plan_blink()

    def _step(self) -> None:
        self._phase = (self._phase + 0.03) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        size = min(self.width(), self.height())
        paint_mascot(painter, size, self._mood, self._phase, self._blinking, self.on_band)


class SpeechBubble(QWidget):
    """What the mascot says: a bubble of dark glass whose tail points right, at the mascot.

    New words fade in over the old ones rather than snapping.
    """

    TAIL = 10
    PADDING = 18
    HEIGHT = 38

    def __init__(self) -> None:
        super().__init__()
        self._text = ""  # what was asked for
        self._shown = ""  # what is drawn, while the old words fade out
        self._ink = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802 (matches QLabel)
        if text == self._text:
            return
        self._text = text
        if motion.enabled() and self.isVisible() and self._shown:
            motion.animate(self, self._ink, 0.0, 110, self._set_ink, on_done=self._swap_and_rise)
        else:
            self._swap()

    def _swap(self) -> None:
        self._shown = self._text
        self.updateGeometry()
        self.update()

    def _swap_and_rise(self) -> None:
        self._swap()
        motion.animate(self, 0.0, 1.0, 220, self._set_ink)

    def _set_ink(self, value: float) -> None:
        self._ink = value
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        width = QFontMetricsF(fonts.serif(15, 500, italic=True)).horizontalAdvance(self._shown)
        return QSize(math.ceil(width) + self.PADDING * 2 + self.TAIL, self.HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self._shown:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(0.5, 0.5, self.width() - self.TAIL - 1, self.height() - 1)
        middle = self.height() / 2
        shape = QPainterPath()
        shape.addRoundedRect(body, 13, 13)
        tail = QPainterPath()
        tail.addPolygon(
            QPolygonF(
                [QPointF(body.right() - 1, middle - 6), QPointF(self.width() - 0.5, middle), QPointF(body.right() - 1, middle + 6)]
            )
        )
        current = theme.current()
        edge = QColor(current.band_gold)
        edge.setAlpha(150)
        glass = QColor(darken(current.band, 0.5))
        glass.setAlpha(190)
        painter.setPen(QPen(edge, 1))
        painter.setBrush(glass)
        painter.drawPath(shape.united(tail))

        painter.setOpacity(self._ink)
        painter.setFont(fonts.serif(15, 500, italic=True))
        painter.setPen(QColor("#f4ecda"))
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self._shown)
