"""The app's own small dialogs: a question with two answers, or a note with one.

They replace Qt's stock message boxes, whose icons and buttons ignore the theme.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QRadialGradient
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLayout, QVBoxLayout, QWidget

from ytgrab import fonts, theme
from ytgrab.mascot import Mascot
from ytgrab.widgets import GoldRule, LuxButton, Text, qc

ZERO_WIDTH_SPACE = "​"


def _breakable(message: str) -> str:
    """Let long paths wrap: a label only breaks lines at spaces, so offer a break after each separator."""
    return message.replace("/", "/" + ZERO_WIDTH_SPACE).replace("\\", "\\" + ZERO_WIDTH_SPACE)


class LuxDialog(QDialog):
    """A heading, a message, the mascot in a fitting mood, and one or two buttons."""

    def __init__(
        self,
        parent: QWidget | None,
        heading: str,
        message: str,
        confirm: str = "OK",
        cancel: str | None = None,
        mood: str = "idle",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ytgrab")
        self.setModal(True)

        figure = Mascot(76, on_band=False)
        figure.set_mood(mood)
        title = Text(heading.upper(), fonts.display(15, 600, 2.6), "ink")
        self.message = Text(_breakable(message), fonts.sans(14), "ink")
        self.message.setWordWrap(True)
        self.message.setFixedWidth(400)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)  # paths can be copied

        words = QVBoxLayout()
        words.setSpacing(12)
        words.addWidget(title)
        words.addWidget(GoldRule())
        words.addWidget(self.message)
        words.addStretch(1)
        top = QHBoxLayout()
        top.setSpacing(22)
        top.addWidget(figure, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(words, 1)

        self.confirm_button = LuxButton(confirm, "primary")
        self.confirm_button.setDefault(True)
        self.confirm_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch(1)
        self.cancel_button: LuxButton | None = None
        if cancel:
            self.cancel_button = LuxButton(cancel, "secondary")
            self.cancel_button.clicked.connect(self.reject)
            buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(22)
        layout.addLayout(top)
        layout.addLayout(buttons)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # exactly as large as its contents

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        current = theme.current()
        painter = QPainter(self)
        rect = QRectF(self.rect())
        painter.fillRect(rect, qc(current.surface))
        light = QRadialGradient(rect.width() / 2, -rect.height() * 0.3, rect.width() * 0.9)
        light.setColorAt(0.0, qc(current.gold, 26 if current.dark else 36))
        light.setColorAt(1.0, qc(current.gold, 0))
        painter.fillRect(rect, light)


def ask(parent: QWidget | None, heading: str, message: str, confirm: str, cancel: str) -> bool:
    """Put a question; True if the confirming button was chosen."""
    return LuxDialog(parent, heading, message, confirm, cancel).exec() == QDialog.DialogCode.Accepted


def tell(parent: QWidget | None, heading: str, message: str, mood: str = "idle") -> None:
    """Show a note with a single button. `mood` is the mascot's: 'happy' for good news, 'sad' for a problem."""
    LuxDialog(parent, heading, message, mood=mood).exec()
