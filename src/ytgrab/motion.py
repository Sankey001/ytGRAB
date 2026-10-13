"""Animation helpers. All motion goes through here, so it can be switched off in one place.

Set YTGRAB_MOTION=off to run without animation: every change then lands at
once. The tests do the same, so what they check never depends on timing.
"""

from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QElapsedTimer, QObject, QTimer, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget
from shiboken6 import isValid

_enabled = os.environ.get("YTGRAB_MOTION", "on").strip().lower() not in {"off", "0", "no", "false"}


def enabled() -> bool:
    return _enabled


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = on
    if not on and _ticker is not None:
        _ticker.clear()


def animate(
    owner: QObject,
    start: float,
    end: float,
    duration: int,
    on_value: Callable[[float], None],
    *,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    delay: int = 0,
    on_done: Callable[[], None] | None = None,
) -> QVariantAnimation | None:
    """Feed `on_value` the numbers from `start` to `end` over `duration` ms.

    The animation belongs to `owner` and dies with it. With motion off,
    `on_value(end)` is called immediately and None is returned.
    """
    if not _enabled or duration <= 0:
        on_value(end)
        if on_done:
            on_done()
        return None

    animation = QVariantAnimation(owner)
    animation.setStartValue(float(start))
    animation.setEndValue(float(end))
    animation.setDuration(duration)
    animation.setEasingCurve(easing)
    animation.valueChanged.connect(lambda value: on_value(float(value)))
    if on_done:
        animation.finished.connect(on_done)

    policy = QAbstractAnimation.DeletionPolicy.DeleteWhenStopped
    if delay > 0:
        on_value(start)
        timer = QTimer(owner)  # a child of the owner, so it cannot fire after the owner is gone
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: animation.start(policy))
        timer.timeout.connect(timer.deleteLater)
        timer.start(delay)
    else:
        animation.start(policy)
    return animation


def stop(animation: QVariantAnimation | None) -> None:
    """Stop an animation returned by `animate`, if it is still running."""
    if animation is not None and isValid(animation):
        animation.stop()


def opacity_of(widget: QWidget) -> float:
    """1.0, or how far a `fade_in` on this widget has got."""
    effect = widget.graphicsEffect()
    return effect.opacity() if isinstance(effect, QGraphicsOpacityEffect) else 1.0


def fade_in(widget: QWidget, duration: int = 460, delay: int = 0, on_frame: Callable[[], None] | None = None) -> None:
    """Fade a widget in from transparent. The effect is removed afterwards, so it costs nothing later."""
    if not _enabled:
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    def step(value: float) -> None:
        if isValid(effect):
            effect.setOpacity(value)
        if on_frame:
            on_frame()

    def finish() -> None:
        if isValid(widget):
            widget.setGraphicsEffect(None)
        if on_frame:
            on_frame()

    animate(widget, 0.0, 1.0, duration, step, delay=delay, on_done=finish)


class _Ticker(QObject):
    """One shared clock, about 30 times a second, for effects that loop. It only runs while someone listens."""

    def __init__(self) -> None:
        super().__init__()
        self._listeners: dict[int, Callable[[float], None]] = {}
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._fire)

    def add(self, listener: QObject, callback: Callable[[float], None]) -> None:
        if not _enabled:
            return
        key = id(listener)
        if key not in self._listeners:
            listener.destroyed.connect(lambda _obj=None, key=key: self._drop(key))
        self._listeners[key] = callback
        if not self._timer.isActive():
            self._clock.start()
            self._timer.start()

    def remove(self, listener: QObject) -> None:
        self._drop(id(listener))

    def clear(self) -> None:
        self._listeners.clear()
        self._timer.stop()

    def _drop(self, key: int) -> None:
        self._listeners.pop(key, None)
        if not self._listeners and isValid(self._timer):  # at exit Qt may already have taken the timer
            self._timer.stop()

    def _fire(self) -> None:
        seconds = self._clock.elapsed() / 1000
        for callback in list(self._listeners.values()):
            callback(seconds)


_ticker: _Ticker | None = None


def ticker() -> _Ticker:
    """The shared clock. Created on first use, once a QApplication exists."""
    global _ticker
    if _ticker is None:
        _ticker = _Ticker()
    return _ticker
