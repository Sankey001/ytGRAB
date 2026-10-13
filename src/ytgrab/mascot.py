"""The header's figurine: an original TV-headed helper, drawn in code, that reacts to what the app is doing.

`paint_mascot` does the drawing and needs only a QPainter, so the same figure
is used for the widget in the header and for the app icon.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

BODY = QColor("#f4f7fd")
SHADE = QColor("#cbd6e9")
OUTLINE = QColor("#0c1528")
SCREEN = QColor("#14213d")
GLOW = QColor("#7fe7ff")
CORAL = QColor("#ff7a59")
GREEN = QColor("#74e3a4")
RED = QColor("#ff8a80")
BLUSH = QColor(255, 157, 176, 160)

MOODS = ("idle", "busy", "happy", "sad")

# Where the hands sit for each mood, in the 120 x 120 drawing space.
HANDS = {
    "idle": ((27, 93), (93, 93)),
    "busy": ((17, 80), (103, 80)),
    "happy": ((12, 66), (108, 66)),
    "sad": ((31, 99), (89, 99)),
}
ANTENNA_TIPS = {"sad": ((33, 12), (87, 12))}  # droop when sad
ANTENNA_UP = ((38, 7), (82, 7))


def paint_mascot(painter: QPainter, size: float, mood: str = "idle", phase: float = 0.0) -> None:
    """Draw the mascot into a `size` x `size` square at the painter's origin.

    `phase` runs 0..1 and drives the busy animation; it is ignored for the other moods.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 120, size / 120)

    bob = math.sin(phase * 2 * math.pi) * 1.6 if mood == "busy" else 0.0
    outline = QPen(OUTLINE, 2.4)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    # The shadow stays on the ground while the body bobs above it.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 70))
    painter.drawEllipse(QPointF(60, 112), 27 - bob, 4.5)
    painter.translate(0, bob)

    _limbs(painter, mood, outline)
    painter.setPen(outline)
    painter.setBrush(BODY)
    painter.drawRoundedRect(QRectF(37, 66, 46, 36), 11, 11)  # torso
    _chest_light(painter, mood, phase)
    _head(painter, mood, phase, outline)
    _face(painter, mood)
    painter.restore()


def _limbs(painter: QPainter, mood: str, outline: QPen) -> None:
    arm = QPen(SHADE, 7)
    arm.setCapStyle(Qt.PenCapStyle.RoundCap)
    left, right = HANDS[mood]
    painter.setPen(arm)
    painter.drawLine(QPointF(40, 80), QPointF(*left))
    painter.drawLine(QPointF(80, 80), QPointF(*right))
    painter.setPen(outline)
    painter.setBrush(BODY)
    for hand in (left, right):
        painter.drawEllipse(QPointF(*hand), 4.6, 4.6)
    painter.setBrush(SHADE)
    painter.drawRoundedRect(QRectF(41, 99, 15, 10), 4.5, 4.5)  # feet
    painter.drawRoundedRect(QRectF(64, 99, 15, 10), 4.5, 4.5)


def _chest_light(painter: QPainter, mood: str, phase: float) -> None:
    """A round display on the chest: play when idle, a falling arrow when busy, a tick or '!' after."""
    centre = QPointF(60, 87)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(SCREEN)
    painter.drawEllipse(centre, 10, 10)

    painter.save()
    clip = QPainterPath()
    clip.addEllipse(centre, 9, 9)
    painter.setClipPath(clip)
    if mood == "idle":
        painter.setBrush(CORAL)
        painter.drawPolygon(QPolygonF([QPointF(57, 82), QPointF(57, 92), QPointF(66, 87)]))
    else:
        pen = QPen({"busy": GLOW, "happy": GREEN, "sad": RED}[mood], 2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if mood == "busy":
            drop = (phase * 2 % 1.0) * 28 - 14  # falls through the display twice per cycle
            painter.drawLine(QPointF(60, 81 + drop), QPointF(60, 92 + drop))
            painter.drawPolyline(
                QPolygonF([QPointF(55.5, 87.5 + drop), QPointF(60, 92 + drop), QPointF(64.5, 87.5 + drop)])
            )
        elif mood == "happy":
            painter.drawPolyline(QPolygonF([QPointF(54.5, 87), QPointF(58.5, 91), QPointF(65.5, 83)]))
        else:
            painter.drawLine(QPointF(60, 81.5), QPointF(60, 88.5))
            painter.drawPoint(QPointF(60, 92.5))
    painter.restore()


def _head(painter: QPainter, mood: str, phase: float, outline: QPen) -> None:
    tips = ANTENNA_TIPS.get(mood, ANTENNA_UP)
    rod = QPen(BODY, 3)
    rod.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(rod)
    painter.drawLine(QPointF(50, 22), QPointF(*tips[0]))
    painter.drawLine(QPointF(70, 22), QPointF(*tips[1]))

    tip_colors = {
        "idle": (CORAL, CORAL),
        "busy": (GLOW, CORAL) if phase < 0.5 else (CORAL, GLOW),  # they take turns blinking
        "happy": (GREEN, GREEN),
        "sad": (SHADE, SHADE),
    }[mood]
    painter.setPen(Qt.PenStyle.NoPen)
    for tip, color in zip(tips, tip_colors):
        painter.setBrush(color)
        painter.drawEllipse(QPointF(*tip), 4.2, 4.2)

    painter.setPen(outline)
    painter.setBrush(BODY)
    painter.drawRoundedRect(QRectF(22, 20, 76, 50), 14, 14)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(SCREEN)
    painter.drawRoundedRect(QRectF(30, 27, 60, 36), 9, 9)


def _face(painter: QPainter, mood: str) -> None:
    line = QPen(GLOW, 2.4)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)

    def curve(start: tuple, bend: tuple, end: tuple) -> QPainterPath:
        path = QPainterPath(QPointF(*start))
        path.quadTo(QPointF(*bend), QPointF(*end))
        return path

    def eyes(y: float, rx: float, ry: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (48, 72):
            painter.setBrush(GLOW)
            painter.drawEllipse(QPointF(x, y), rx, ry)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(x + 1.6, y - ry * 0.4), 1.4, 1.4)

    def stroke() -> None:
        painter.setPen(line)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    if mood == "idle":
        eyes(43, 4.5, 6.5)
        stroke()
        painter.drawPath(curve((53, 53), (60, 58.5), (67, 53)))
    elif mood == "busy":  # looking down at the chest light
        eyes(46, 4.6, 4.6)
        stroke()
        painter.drawEllipse(QPointF(60, 56), 2.6, 2.6)
    elif mood == "happy":
        stroke()
        painter.drawPath(curve((43, 46), (48, 37), (53, 46)))
        painter.drawPath(curve((67, 46), (72, 37), (77, 46)))
        smile = curve((52, 51), (60, 62), (68, 51))
        smile.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(GLOW)
        painter.drawPath(smile)
        painter.setBrush(BLUSH)
        painter.drawEllipse(QPointF(38, 53), 4, 2.6)
        painter.drawEllipse(QPointF(82, 53), 4, 2.6)
    else:  # sad
        eyes(46, 3.6, 4.2)
        stroke()
        painter.drawLine(QPointF(43, 39.5), QPointF(52, 36.5))  # brows raised in the middle: worried
        painter.drawLine(QPointF(77, 39.5), QPointF(68, 36.5))
        painter.drawPath(curve((54, 58), (60, 53), (66, 58)))


class Mascot(QWidget):
    """The figurine as a widget. Moods: idle, busy (animated), happy, sad."""

    def __init__(self, size: int = 88) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self._mood = "idle"
        self._phase = 0.0  # 0..1, only advances while busy
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._step)

    def mood(self) -> str:
        return self._mood

    def set_mood(self, mood: str) -> None:
        if mood == self._mood or mood not in MOODS:
            return
        self._mood = mood
        self._phase = 0.0
        if mood == "busy":
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _step(self) -> None:
        self._phase = (self._phase + 0.03) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        paint_mascot(painter, min(self.width(), self.height()), self._mood, self._phase)


class SpeechBubble(QWidget):
    """A rounded bubble whose tail points right, at the mascot."""

    TAIL = 9

    def __init__(self) -> None:
        super().__init__()
        self._label = QLabel()
        self._label.setStyleSheet("color: #10203a; font-size: 13px; font-weight: 600; background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 9, 14 + self.TAIL, 9)
        layout.addWidget(self._label)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def text(self) -> str:
        return self._label.text()

    def setText(self, text: str) -> None:  # noqa: N802 (matches QLabel)
        self._label.setText(text)
        self.updateGeometry()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(0, 0, self.width() - self.TAIL, self.height())
        middle = self.height() / 2
        shape = QPainterPath()
        shape.addRoundedRect(body, 12, 12)
        tail = QPainterPath()
        tail.addPolygon(
            QPolygonF(
                [QPointF(body.right() - 1, middle - 6), QPointF(self.width(), middle), QPointF(body.right() - 1, middle + 6)]
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#eaf2ff"))
        painter.drawPath(shape.united(tail))
