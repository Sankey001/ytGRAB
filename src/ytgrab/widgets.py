"""The custom-drawn pieces of the window: backdrop, panels, buttons, progress bars and small ornaments.

Each one reads `theme.current()` when it paints, so changing the theme only needs a repaint.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ytgrab import fonts, motion, theme
from ytgrab.theme import darken, lighten, mix

BAND_INK = "#f4ecda"  # text on the header band, which is deep in every theme


def qc(color: str, alpha: int = 255) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, int(alpha))))
    return result


_stripe_cache: dict[tuple[str, int], QPixmap] = {}


def pinstripes(color: str, alpha: int) -> QPixmap:
    """A tile of faint vertical pinstripes, to lay over a flat colour."""
    key = (color, alpha)
    if key not in _stripe_cache:
        tile = QPixmap(7, 7)
        tile.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tile)
        painter.fillRect(0, 0, 1, 7, qc(color, alpha))
        painter.end()
        _stripe_cache[key] = tile
    return _stripe_cache[key]


def paint_shadow(painter: QPainter, rect: QRectF, radius: float, strength: float) -> None:
    """A soft shadow below `rect`, built from a few translucent layers rather than a blur."""
    if strength <= 0:
        return
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    layers = 8
    for layer in range(layers, 0, -1):
        spread = layer * 2.4
        fade = (1 - layer / (layers + 1)) ** 2
        painter.setBrush(QColor(0, 0, 0, int(strength * fade * 0.26)))
        painter.drawRoundedRect(
            rect.adjusted(-spread * 0.7, -spread * 0.3 + 3, spread * 0.7, spread + 5), radius + spread, radius + spread
        )
    painter.restore()


# ------------------------------------------------------------------ surfaces


class Canvas(QWidget):
    """The window's body: the backdrop, and the shadows under the panels placed on it."""

    def __init__(self) -> None:
        super().__init__()
        self._panels: list[QWidget] = []

    def add_panel(self, panel: QWidget) -> None:
        self._panels.append(panel)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        painter.fillRect(rect, qc(current.base))
        light = QRadialGradient(rect.width() / 2, -rect.height() * 0.2, rect.width() * 0.8)
        light.setColorAt(0.0, qc(current.gold, 20 if current.dark else 30))
        light.setColorAt(1.0, qc(current.gold, 0))
        painter.fillRect(rect, light)

        for panel in self._panels:
            if panel.isVisible():
                paint_shadow(painter, QRectF(panel.geometry()), Panel.RADIUS, current.shadow * motion.opacity_of(panel))


class Panel(QWidget):
    """A raised card with a hairline border."""

    RADIUS = theme.RADIUS_PANEL

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        fill = QLinearGradient(0, rect.top(), 0, rect.bottom())
        fill.setColorAt(0.0, qc(lighten(current.surface, 0.035) if current.dark else current.surface))
        fill.setColorAt(1.0, qc(current.surface))
        painter.setPen(QPen(qc(current.hairline), 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        # a single lighter line just inside the top edge, as if lit from above
        painter.setPen(QPen(qc("#ffffff", 16 if current.dark else 150), 1))
        painter.drawLine(
            QPointF(rect.left() + self.RADIUS, rect.top() + 1.5), QPointF(rect.right() - self.RADIUS, rect.top() + 1.5)
        )


class HeaderBand(QWidget):
    """The deep band across the top, closed off by a gold rule."""

    HEIGHT = 96

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(self.HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        sweep = QLinearGradient(0, 0, 0, rect.height())  # deeper at the top, like cloth lit from below
        sweep.setColorAt(0.0, qc(darken(current.band, 0.42)))
        sweep.setColorAt(1.0, qc(current.band))
        painter.fillRect(rect, sweep)
        painter.drawTiledPixmap(self.rect(), pinstripes("#ffffff", 5))

        rule = QLinearGradient(0, 0, rect.width(), 0)
        for position, alpha in ((0.0, 0), (0.18, 170), (0.82, 170), (1.0, 0)):
            rule.setColorAt(position, qc(current.band_gold, alpha))
        painter.fillRect(QRectF(0, rect.height() - 1, rect.width(), 1), rule)


class FooterBand(QWidget):
    """The quiet strip along the bottom."""

    HEIGHT = 46

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(self.HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.fillRect(self.rect(), qc(mix(current.base, current.surface, 0.6)))
        painter.fillRect(QRectF(0, 0, self.width(), 1), qc(current.hairline))


class GoldRule(QWidget):
    """A hairline that fades out at both ends."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(1)

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        rule = QLinearGradient(0, 0, self.width(), 0)
        for position, alpha in ((0.0, 0), (0.12, 150), (0.88, 150), (1.0, 0)):
            rule.setColorAt(position, qc(current.gold, alpha))
        painter.fillRect(self.rect(), rule)


class RuledRow(QWidget):
    """A row of controls between two hairlines that fade out at the ends, as on a printed menu."""

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        rule = QLinearGradient(0, 0, self.width(), 0)
        for position, alpha in ((0.0, 0), (0.08, 255), (0.92, 255), (1.0, 0)):
            rule.setColorAt(position, qc(current.hairline, alpha))
        painter.fillRect(QRectF(0, 0, self.width(), 1), rule)
        painter.fillRect(QRectF(0, self.height() - 1, self.width(), 1), rule)


# ---------------------------------------------------------------------- text


class Text(QLabel):
    """A label whose colour is a theme role, so it follows theme changes (see `retint`).

    With `elide`, the label never asks for width: it takes what the layout has
    left and ends in an ellipsis when its words do not fit.
    """

    def __init__(self, text: str = "", font: QFont | None = None, role: str = "ink", elide: bool = False) -> None:
        super().__init__(text)
        self.role = role
        self.elide = elide
        if font is not None:
            self.setFont(font)
        if elide:
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.setMinimumWidth(40)
        self.retint()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self.elide:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        shown = QFontMetricsF(self.font()).elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shown)

    def retint(self) -> None:
        current = theme.current()
        color = {
            "ink": current.ink,
            "muted": current.muted,
            "gold": current.gold,
            "band_ink": BAND_INK,
            "band_gold": current.band_gold,
        }[self.role]
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, qc(color))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, qc(current.disabled))
        self.setPalette(palette)


class Medallion(QWidget):
    """A section numeral in a quiet ring."""

    SIZE = 30

    def __init__(self, numeral: str) -> None:
        super().__init__()
        self.numeral = numeral
        self.setFixedSize(self.SIZE, self.SIZE)

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        centre = QPointF(self.SIZE / 2, self.SIZE / 2)

        painter.setBrush(qc(current.gold, 14))
        painter.setPen(QPen(qc(current.ornament), 1))
        painter.drawEllipse(centre, self.SIZE / 2 - 1, self.SIZE / 2 - 1)

        painter.setPen(qc(mix(current.ornament, current.gold, 0.5)))
        painter.setFont(fonts.display(12, 700))
        painter.drawText(QRectF(self.rect()).adjusted(0, -0.5, 0, -0.5), Qt.AlignmentFlag.AlignCenter, self.numeral)


class Pill(QLabel):
    """A small outlined tag, such as the kind of link in a row. Empty text draws nothing."""

    WIDTH = 96

    def __init__(self) -> None:
        super().__init__()
        self.kind = ""
        self.setFixedSize(self.WIDTH, 24)
        self.setVisible(False)

    def set_kind(self, kind: str, text: str) -> None:
        """Show `text` in the colours of `kind`. With no text the tag takes no room; it slides in when given some."""
        appearing = bool(text) and not self.text()
        self.kind = kind
        self.setText(text)
        self.setVisible(bool(text))
        if appearing:
            motion.animate(self, 0.0, self.WIDTH, 180, lambda width: self.setFixedWidth(max(1, round(width))))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self.text():
            return
        current = theme.current()
        tone = {
            "video": current.gold,
            "playlist": lighten(current.jewel, 0.42) if current.dark else current.jewel,
            "invalid": current.failed,
        }.get(self.kind, current.muted)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(qc(tone, 150), 1))
        painter.setBrush(qc(tone, 22))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        tracking = 1.5
        painter.setFont(fonts.sans(10.5, QFont.Weight.DemiBold, tracking))
        painter.setPen(qc(tone))
        painter.drawText(rect.adjusted(tracking, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, self.text().upper())


# ------------------------------------------------------------------- buttons


class LuxButton(QPushButton):
    """A button that paints itself: 'primary' (filled), 'secondary' (outlined) or 'quiet' (text only).

    Hover eases in and out, and a primary button gets a band of light sweeping across it when the pointer arrives.
    """

    RADIUS = theme.RADIUS_CONTROL

    def __init__(self, text: str = "", kind: str = "secondary", small: bool = False, glyph: str = "") -> None:
        super().__init__(text)
        self.kind = kind
        self.small = small
        self.glyph = glyph  # 'close', 'minus' or 'plus': a drawn mark instead of text
        self._hover = 0.0
        self._sheen = 1.0  # 0..1 while the band of light crosses; 1 means it is off
        self._hover_run = None
        self._keyboard_focus = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    # --- size

    def _font(self) -> QFont:
        return fonts.sans(11 if self.small else 12, QFont.Weight.DemiBold, self._tracking())

    def _tracking(self) -> float:
        return 1.2 if self.small else 1.5

    def _label(self) -> str:
        return self.text().upper()

    def sizeHint(self) -> QSize:  # noqa: N802
        if self.glyph:
            return QSize(theme.COMPACT_HEIGHT, theme.COMPACT_HEIGHT)
        width = QFontMetricsF(self._font()).horizontalAdvance(self._label())
        padding = 12 if self.kind == "quiet" else (16 if self.small else 26)
        return QSize(math.ceil(width) + padding * 2, theme.COMPACT_HEIGHT if self.small else theme.CONTROL_HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    # --- motion

    def _set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    def _set_sheen(self, value: float) -> None:
        self._sheen = value
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        motion.stop(self._hover_run)
        self._hover_run = motion.animate(self, self._hover, 1.0, 170, self._set_hover)
        if self.kind == "primary" and self.isEnabled():
            motion.animate(self, 0.0, 1.0, 620, self._set_sheen, easing=QEasingCurve.Type.InOutSine)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        motion.stop(self._hover_run)
        self._hover_run = motion.animate(self, self._hover, 0.0, 260, self._set_hover)
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        self._keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._keyboard_focus = False
        super().focusOutEvent(event)

    # --- drawing

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        enabled, down, hover = self.isEnabled(), self.isDown(), self._hover
        shape = QPainterPath()
        shape.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        if self.kind == "primary":
            text_color = self._paint_primary(painter, current, rect, shape, enabled, down, hover)
        elif self.kind == "secondary":
            text_color = self._paint_secondary(painter, current, shape, enabled, down, hover)
        else:
            text_color = self._paint_quiet(painter, current, rect, shape, enabled, down, hover)

        if self._keyboard_focus and self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qc(current.gold, 190), 1.4))
            painter.drawRoundedRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5), self.RADIUS + 1, self.RADIUS + 1)

        nudge = 1 if down and enabled else 0
        if self.glyph:
            self._paint_glyph(painter, rect.center() + QPointF(0, nudge), text_color)
            return
        painter.setFont(self._font())
        painter.setPen(qc(text_color))
        painter.drawText(rect.adjusted(self._tracking(), nudge, 0, nudge), Qt.AlignmentFlag.AlignCenter, self._label())

    def _paint_glyph(self, painter: QPainter, centre: QPointF, color: str) -> None:
        pen = QPen(qc(color), 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        reach = 4.5
        if self.glyph == "close":
            painter.drawLine(centre + QPointF(-reach, -reach), centre + QPointF(reach, reach))
            painter.drawLine(centre + QPointF(-reach, reach), centre + QPointF(reach, -reach))
            return
        painter.drawLine(centre + QPointF(-reach, 0), centre + QPointF(reach, 0))
        if self.glyph == "plus":
            painter.drawLine(centre + QPointF(0, -reach), centre + QPointF(0, reach))

    def _paint_primary(self, painter, current, rect, shape, enabled, down, hover) -> str:
        if not enabled:
            painter.setPen(QPen(qc(current.line), 1))
            painter.setBrush(qc(mix(current.surface, current.ink, 0.06)))
            painter.drawPath(shape)
            return current.disabled

        accent = mix(current.accent, current.accent_hover, hover)
        if down:
            accent = current.accent_down
        fill = QLinearGradient(0, rect.top(), 0, rect.bottom())  # brushed metal, not chrome: a slight shade only
        fill.setColorAt(0.0, qc(lighten(accent, 0.12)))
        fill.setColorAt(1.0, qc(darken(accent, 0.1)))
        painter.setPen(QPen(qc(darken(accent, 0.3)), 1))
        painter.setBrush(fill)
        painter.drawPath(shape)

        painter.save()
        painter.setClipPath(shape)
        painter.setPen(QPen(qc("#ffffff", 55), 1))  # the lit top edge
        painter.drawLine(QPointF(rect.left(), rect.top() + 1.5), QPointF(rect.right(), rect.top() + 1.5))
        if self._sheen < 1.0:
            width = rect.height() * 1.6
            x = rect.left() - width + (rect.width() + width * 2) * self._sheen
            band = QLinearGradient(x, 0, x + width, 0)
            band.setColorAt(0.0, qc("#ffffff", 0))
            band.setColorAt(0.5, qc("#ffffff", 95))
            band.setColorAt(1.0, qc("#ffffff", 0))
            slant = rect.height() * 0.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(band)
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x + slant, rect.top()),
                        QPointF(x + width + slant, rect.top()),
                        QPointF(x + width, rect.bottom()),
                        QPointF(x, rect.bottom()),
                    ]
                )
            )
        painter.restore()
        return current.on_accent

    def _paint_secondary(self, painter, current, shape, enabled, down, hover) -> str:
        if not enabled:
            painter.setPen(QPen(qc(current.line), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(shape)
            return current.disabled
        lift = 0.03 + 0.07 * hover - (0.02 if down else 0)
        painter.setPen(QPen(qc(mix(current.hairline_strong, current.gold, hover)), 1))
        painter.setBrush(qc(mix(current.surface, current.ink, lift)))
        painter.drawPath(shape)
        return current.ink

    def _paint_quiet(self, painter, current, rect, shape, enabled, down, hover) -> str:
        if not enabled:
            return current.disabled
        active = self.isChecked()
        if hover > 0 or active or down:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qc(current.ink, int(26 * max(hover, 1.0 if active else 0.0)) + (10 if down else 0)))
            painter.drawPath(shape)
        if active:
            painter.fillRect(QRectF(rect.left() + 10, rect.bottom() - 4, rect.width() - 20, 1.5), qc(current.gold))
        return mix(current.muted, current.gold, max(hover, 1.0 if active else 0.0))


class Stepper(QWidget):
    """A small number with a minus and a plus beside it."""

    valueChanged = Signal(int)  # noqa: N815 (matches QSpinBox)

    def __init__(self, low: int = 1, high: int = 6, value: int = 1) -> None:
        super().__init__()
        self._low, self._high, self._value = low, high, value
        self.minus = LuxButton("", "secondary", small=True, glyph="minus")
        self.plus = LuxButton("", "secondary", small=True, glyph="plus")
        self.minus.setAccessibleName("Fewer")
        self.plus.setAccessibleName("More")
        for button, step in ((self.minus, -1), (self.plus, 1)):
            button.setFixedSize(theme.COMPACT_HEIGHT, theme.COMPACT_HEIGHT)
            button.setAutoRepeat(True)
            button.clicked.connect(lambda _checked=False, step=step: self.setValue(self._value + step))
        self.figure = Text(str(value), fonts.serif(18, 600, lining=True), "ink")
        self.figure.setFixedWidth(26)
        self.figure.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.minus)
        layout.addWidget(self.figure)
        layout.addWidget(self.plus)
        self.setValue(value)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:  # noqa: N802
        value = max(self._low, min(self._high, int(value)))
        changed = value != self._value
        self._value = value
        self.figure.setText(str(value))
        self.minus.setEnabled(value > self._low)
        self.plus.setEnabled(value < self._high)
        if changed:
            self.valueChanged.emit(value)


# ------------------------------------------------------------------ progress


class GoldBar(QWidget):
    """A progress bar that eases to each new value and shimmers while work is under way.

    The plain form (the table rows) is a slim track with its status written above it. The `grand`
    form is the overall bar: no text, quarter marks below, and a jewel riding the leading edge.
    States: 'idle', 'active', 'done', 'failed'.
    """

    shown = Signal(float)  # the fraction on screen right now, as it eases
    GRAND_INSET = 9  # how far the grand bar's track sits in from the widget's edges
    HEIGHT = 28
    TRACK = 4  # thickness of a row's track

    def __init__(self, grand: bool = False) -> None:
        super().__init__()
        self.grand = grand
        self._target = 0.0
        self._shown = 0.0
        self._text = ""
        self._state = "idle"
        self._phase = 0.0  # where the shimmer is, 0..1
        self._glint = 1.0  # a single pass of light when the bar completes; 1 means off
        self._run = None
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(60)

    def fraction(self) -> float:
        return self._target

    def text(self) -> str:
        return self._text

    def state(self) -> str:
        return self._state

    def set_progress(self, fraction: float | None = None, text: str | None = None, state: str | None = None) -> None:
        if text is not None:
            self._text = text
        if state is not None and state != self._state:
            self._state = state
            if state == "active":
                motion.ticker().add(self, self._on_tick)
            else:
                motion.ticker().remove(self)
            if state == "done":
                motion.animate(self, 0.0, 1.0, 900, self._set_glint, easing=QEasingCurve.Type.InOutSine)
        if fraction is not None:
            fraction = max(0.0, min(1.0, fraction))
            motion.stop(self._run)
            self._target = fraction
            if fraction < self._shown:  # a reset should not crawl backwards
                self._set_shown(fraction)
            else:
                self._run = motion.animate(self, self._shown, fraction, 420, self._set_shown)
        self.update()

    def _set_shown(self, value: float) -> None:
        self._shown = value
        self.shown.emit(value)
        self.update()

    def _set_glint(self, value: float) -> None:
        self._glint = value
        self.update()

    def _on_tick(self, seconds: float) -> None:
        self._phase = (seconds * 0.6) % 1.0
        self.update()

    # --- drawing

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.grand:
            track = QRectF(self.GRAND_INSET, 8, self.width() - self.GRAND_INSET * 2, 8)
        else:
            track = QRectF(0.5, self.height() - self.TRACK - 1.5, self.width() - 1, self.TRACK)
        radius = track.height() / 2
        shape = QPainterPath()
        shape.addRoundedRect(track, radius, radius)

        if not self.grand and self._state == "idle" and not self._text and self._shown <= 0:
            return  # a row with nothing to report yet stays blank

        painter.setPen(QPen(qc(current.line), 1))
        painter.setBrush(qc(current.field))
        painter.drawPath(shape)

        tone = self._tone(current)
        filled = QRectF(track.left(), track.top(), track.width() * self._shown, track.height())
        if filled.width() > 0.5:
            painter.save()
            painter.setClipPath(shape)
            metal = QLinearGradient(0, track.top(), 0, track.bottom())
            metal.setColorAt(0.0, qc(lighten(tone, 0.26)))
            metal.setColorAt(0.5, qc(tone))
            metal.setColorAt(1.0, qc(darken(tone, 0.22)))
            painter.fillRect(filled, metal)
            if self._state == "active":
                self._paint_light(painter, filled, self._phase, 80)
            if self._glint < 1.0:
                self._paint_light(painter, filled, self._glint, 120)
            painter.restore()

        if self.grand:
            self._paint_grand_details(painter, current, track)
        elif self._text:
            self._paint_label(painter, current)

    def _tone(self, current) -> str:
        """The colour of the filled part: the accent while working, calmer once a row has come to rest."""
        if self._state == "failed":
            return mix(current.failed, current.surface, 0.25)
        if self.grand or self._state == "active":
            return current.accent
        if self._state == "done":
            return current.done
        return mix(current.accent, current.surface, 0.55)  # stopped part-way

    @staticmethod
    def _paint_light(painter: QPainter, filled: QRectF, position: float, strength: int) -> None:
        """A soft band of light somewhere along the filled part."""
        width = max(70.0, filled.width() * 0.35)
        x = filled.left() - width + (filled.width() + width) * position
        light = QLinearGradient(x, 0, x + width, 0)
        light.setColorAt(0.0, qc("#ffffff", 0))
        light.setColorAt(0.5, qc("#ffffff", strength))
        light.setColorAt(1.0, qc("#ffffff", 0))
        painter.fillRect(filled, light)

    def _paint_label(self, painter: QPainter, current) -> None:
        """The status in words above the track, with a tick once the row is done."""
        color = {"idle": current.muted, "done": current.done, "failed": current.failed}.get(self._state, current.ink)
        area = QRectF(1, 0, self.width() - 2, self.height() - self.TRACK - 6)
        left = area.left()
        if self._state == "done":
            pen = QPen(qc(color), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            middle = area.center().y()
            painter.drawPolyline(
                QPolygonF([QPointF(left + 1, middle + 0.5), QPointF(left + 4.2, middle + 3.6), QPointF(left + 10, middle - 3)])
            )
            left += 16
        font = fonts.sans(12, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(qc(color))
        room = QRectF(left, area.top(), area.right() - left, area.height())
        words = QFontMetricsF(font).elidedText(self._text, Qt.TextElideMode.ElideRight, room.width())
        painter.drawText(room, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, words)

    def _paint_grand_details(self, painter: QPainter, current, track: QRectF) -> None:
        painter.setPen(QPen(qc(current.ornament, 170), 1))
        for quarter in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = round(track.left() + track.width() * quarter) + 0.5
            reach = 5 if quarter in (0.0, 0.5, 1.0) else 3  # longer marks at the ends and the middle
            painter.drawLine(QPointF(x, track.bottom() + 4), QPointF(x, track.bottom() + 4 + reach))

        if self._state == "idle" and self._shown <= 0:
            return
        # the jewel: a small lozenge on the leading edge
        centre = QPointF(track.left() + track.width() * self._shown, track.center().y())
        reach = 7.0
        lozenge = QPolygonF(
            [
                QPointF(centre.x(), centre.y() - reach),
                QPointF(centre.x() + reach, centre.y()),
                QPointF(centre.x(), centre.y() + reach),
                QPointF(centre.x() - reach, centre.y()),
            ]
        )
        painter.setPen(QPen(qc(darken(current.accent, 0.35)), 1))
        painter.setBrush(qc(lighten(current.accent, 0.3)))
        painter.drawPolygon(lozenge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qc(current.surface))
        painter.drawEllipse(centre, 2.1, 2.1)


class Figure(QWidget):
    """A large percentage in the serif face."""

    def __init__(self) -> None:
        super().__init__()
        self._fraction = 0.0
        self.setFixedSize(96, 46)

    def set_fraction(self, fraction: float) -> None:
        self._fraction = fraction
        self.update()

    def text(self) -> str:
        return f"{math.floor(self._fraction * 100 + 1e-6)}%"

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(fonts.serif(36, 600, lining=True))
        painter.setPen(qc(theme.current().gold))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class OverallProgress(QWidget):
    """The whole batch at a glance: a large figure, the grand bar, and a line of detail under it."""

    def __init__(self) -> None:
        super().__init__()
        self.figure = Figure()
        self.bar = GoldBar(grand=True)
        self.caption = Text("", fonts.sans(12.5), "muted", elide=True)
        self.bar.shown.connect(self.figure.set_fraction)

        caption_row = QHBoxLayout()  # indented so the words start where the track does
        caption_row.setContentsMargins(GoldBar.GRAND_INSET, 0, GoldBar.GRAND_INSET, 0)
        caption_row.addWidget(self.caption, 1)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(self.bar)
        column.addLayout(caption_row)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 0)  # room for the rule that sets the readout apart from the list
        layout.setSpacing(6)
        layout.addWidget(self.figure)
        layout.addLayout(column, 1)

    def paintEvent(self, _event) -> None:  # noqa: N802
        QPainter(self).fillRect(QRectF(0, 0, self.width(), 1), qc(theme.current().hairline))

    def set_progress(self, fraction: float | None = None, state: str | None = None) -> None:
        self.bar.set_progress(fraction, None, state)

    def fraction(self) -> float:
        return self.bar.fraction()


# -------------------------------------------------------------- small pieces


class Swatch(QAbstractButton):
    """One theme, as a small disc in its own colours."""

    def __init__(self, shown: theme.Theme) -> None:
        super().__init__()
        self.shown = shown
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedSize(26, 26)
        self.setToolTip(shown.name)
        self.setAccessibleName(f"{shown.name} theme")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        centre = QPointF(self.width() / 2, self.height() / 2)
        if self.isChecked() or self.underMouse() or self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qc(theme.current().gold, 255 if self.isChecked() or self.hasFocus() else 130), 1.4))
            painter.drawEllipse(centre, 11.5, 11.5)
        painter.setPen(QPen(qc(mix(self.shown.surface, self.shown.gold, 0.5)), 1))
        painter.setBrush(qc(self.shown.band if self.shown.dark else self.shown.surface))
        painter.drawEllipse(centre, 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qc(self.shown.accent))
        painter.drawEllipse(centre, 3.2, 3.2)


class ThemePicker(QWidget):
    """A row of swatches, one per theme."""

    chosen = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.swatches: dict[str, Swatch] = {}
        for key, shown in theme.THEMES.items():
            swatch = Swatch(shown)
            swatch.clicked.connect(lambda _checked=False, key=key: self.chosen.emit(key))
            self.swatches[key] = swatch
            layout.addWidget(swatch)

    def set_current(self, key: str) -> None:
        if key in self.swatches:
            self.swatches[key].setChecked(True)


class Emblem(QWidget):
    """The mark at the head of the window: a monogram in a double gold ring, or your own picture in that frame."""

    SIZE = 60

    def __init__(self, image_path: str | None = None, letters: str = "YG") -> None:
        super().__init__()
        self.setFixedSize(self.SIZE, self.SIZE)
        self.letters = letters
        self._source = QPixmap(image_path) if image_path else QPixmap()
        self._scaled: QPixmap | None = None

    def paintEvent(self, _event) -> None:  # noqa: N802
        current = theme.current()
        gold = current.band_gold
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        centre = QPointF(self.SIZE / 2, self.SIZE / 2)
        reach = self.SIZE / 2 - 1.2

        painter.setPen(QPen(qc(gold), 1.5))
        painter.setBrush(qc(darken(current.band, 0.35), 170))
        painter.drawEllipse(centre, reach, reach)

        if not self._source.isNull():
            self._paint_picture(painter, centre, reach - 4)
            return
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qc(gold, 130), 1))
        painter.drawEllipse(centre, reach - 5, reach - 5)
        tracking = 1.2
        painter.setFont(fonts.display(19, 600, tracking))
        painter.setPen(qc(gold))
        painter.drawText(QRectF(self.rect()).adjusted(tracking, -1, 0, -1), Qt.AlignmentFlag.AlignCenter, self.letters)

    def _paint_picture(self, painter: QPainter, centre: QPointF, reach: float) -> None:
        """The picture, scaled to fill the ring and cropped to a circle."""
        side = round(reach * 2 * self.devicePixelRatioF())
        if self._scaled is None or min(self._scaled.width(), self._scaled.height()) != side:
            self._scaled = self._source.scaled(
                side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
        clip = QPainterPath()
        clip.addEllipse(centre, reach, reach)
        painter.setClipPath(clip)
        middle = QRectF((self._scaled.width() - side) / 2, (self._scaled.height() - side) / 2, side, side)
        painter.drawPixmap(QRectF(centre.x() - reach, centre.y() - reach, reach * 2, reach * 2), self._scaled, middle)


class _Fade(QWidget):
    """A veil over the foot of a list, shown while more rows wait below. Clicks pass through it."""

    HEIGHT = 34

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def paintEvent(self, _event) -> None:  # noqa: N802
        surface = theme.current().surface
        veil = QLinearGradient(0, 0, 0, self.height())
        veil.setColorAt(0.0, qc(surface, 0))
        veil.setColorAt(1.0, qc(surface, 245))
        QPainter(self).fillRect(self.rect(), veil)


class HintedTable(QTableWidget):
    """A table that says what it is for while it has no rows, and fades out where its rows run on."""

    def __init__(self, rows: int, columns: int, headline: str, detail: str) -> None:
        super().__init__(rows, columns)
        self.headline, self.detail = headline, detail
        self._fade = _Fade(self)
        self.verticalScrollBar().valueChanged.connect(self._place_fade)
        self.verticalScrollBar().rangeChanged.connect(self._place_fade)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_fade()

    def _place_fade(self, *_args) -> None:
        bar = self.verticalScrollBar()
        area = self.viewport().geometry()
        self._fade.setGeometry(area.left(), area.bottom() + 1 - _Fade.HEIGHT, area.width(), _Fade.HEIGHT)
        self._fade.setVisible(bar.value() < bar.maximum())
        self._fade.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.rowCount():
            return
        current = theme.current()
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.viewport().rect())
        centre = QPointF(area.center().x(), area.center().y() - 26)

        # a short rule with a lozenge at its middle
        rule = QLinearGradient(centre.x() - 90, 0, centre.x() + 90, 0)
        for position, alpha in ((0.0, 0), (0.35, 160), (0.65, 160), (1.0, 0)):
            rule.setColorAt(position, qc(current.gold, alpha))
        painter.fillRect(QRectF(centre.x() - 90, centre.y(), 180, 1), rule)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qc(current.gold))
        painter.drawPolygon(
            QPolygonF([centre + QPointF(0, -4.5), centre + QPointF(4.5, 0.5), centre + QPointF(0, 5.5), centre + QPointF(-4.5, 0.5)])
        )

        painter.setPen(qc(mix(current.ink, current.muted, 0.45)))
        painter.setFont(fonts.serif(19, italic=True))
        painter.drawText(QRectF(area.left(), centre.y() + 14, area.width(), 30), Qt.AlignmentFlag.AlignCenter, self.headline)
        painter.setPen(qc(current.muted))
        painter.setFont(fonts.sans(12.5))
        painter.drawText(QRectF(area.left(), centre.y() + 46, area.width(), 22), Qt.AlignmentFlag.AlignCenter, self.detail)


class RowRule(QStyledItemDelegate):
    """Table cells with a little side padding and a hairline under each row.

    Only the `loud` column is written in full ink; the rest step back, so a row reads title first.
    """

    def __init__(self, parent=None, loud: int = -1) -> None:
        super().__init__(parent)
        self.loud = loud

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        padded = QStyleOptionViewItem(option)
        padded.rect = option.rect.adjusted(6, 0, -6, 0)
        if self.loud >= 0 and index.column() != self.loud:
            quiet = qc(theme.current().muted)
            for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):  # disabled rows stay faint
                padded.palette.setColor(group, QPalette.ColorRole.Text, quiet)
        super().paint(painter, padded, index)
        painter.save()
        painter.setPen(QPen(qc(theme.current().hairline), 1))
        y = option.rect.bottom() + 0.5
        painter.drawLine(QPointF(option.rect.left(), y), QPointF(option.rect.right() + 1, y))
        painter.restore()
