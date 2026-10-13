"""The ytgrab window: links in, a table of videos with qualities and sizes, downloads out."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QDir,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QStandardPaths,
    Qt,
    QTemporaryDir,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QStyledItemDelegate,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shiboken6 import isValid

from ytgrab import __version__, dialogs, fonts, launcher, motion, theme, tools, ytdlp
from ytgrab.eta import SpeedMeter
from ytgrab.formats import (
    DEFAULT_HEIGHT,
    STANDARD_HEIGHTS,
    Quality,
    human_eta,
    human_size,
    human_time,
    pick_default,
    qualities,
)
from ytgrab.mascot import Mascot, SpeechBubble
from ytgrab.urls import UrlKind, classify, normalize, split_links
from ytgrab.widgets import (
    Canvas,
    Emblem,
    FooterBand,
    GoldBar,
    HeaderBand,
    HintedTable,
    LuxButton,
    Medallion,
    OverallProgress,
    Panel,
    Pill,
    RowRule,
    RuledRow,
    Stepper,
    Text,
    ThemePicker,
)

# Lookups running at once when listing. Measured on a 9-video playlist:
# 4 at once took about 7.5 s, 6 took 4.5 s, and 8 was no faster than 6.
FETCH_PARALLEL = min(6, max(3, (os.cpu_count() or 4) // 2))
DEFAULT_DOWNLOADS = 3  # videos downloading at once
MIN_BYTES_FOR_SPEED = 5 * 1024 * 1024  # don't remember a speed measured on a tiny download
SAVED_INFO_MAX_AGE = 4 * 3600  # seconds; the links inside a lookup's answer expire after some hours

CONTROL_HEIGHT = theme.CONTROL_HEIGHT  # text fields, dropdowns and buttons share one height
COMPACT_HEIGHT = theme.COMPACT_HEIGHT  # the same, where room is short: table rows, the options row
PANEL_PADDING = 24  # between a panel's edge and what is in it
ROW_HEIGHT = 48
BODY_MARGINS = (30, 24, 30, 24)
BODY_SPACING = 18  # gap between the panels
LOG_HEIGHT = 120
WINDOW_FRAME_ALLOWANCE = 48  # title bar and a little slack when sizing to the screen
MAX_LINK_ROWS_SHOWN = 3  # more links than this scroll
ROW_REVEAL_LIMIT = 24  # a longer list appears at once instead of unfolding row by row

COL_PICK, COL_TITLE, COL_LENGTH, COL_QUALITY, COL_SIZE, COL_PROGRESS = range(6)
HEADERS = ["#", "Title", "Length", "Quality", "Size", "Progress"]

# The tag shown beside a link field, by what the link is.
LINK_KINDS = {
    UrlKind.VIDEO: "video",
    UrlKind.PLAYLIST: "playlist",
    UrlKind.OTHER: "other",
    UrlKind.INVALID: "invalid",
}
FETCHABLE = (UrlKind.VIDEO, UrlKind.PLAYLIST, UrlKind.OTHER)

# What the mascot shows and says for each situation: (mood, speech bubble).
MOODS = {
    "idle": ("idle", "At your service. Drop a link to begin."),
    "listing": ("busy", "Checking what's available…"),
    "ready": ("idle", "Choose the qualities, then Download."),
    "downloading": ("busy", "Downloading…"),
    "done": ("happy", "All done."),
    "failed": ("sad", "Some downloads failed."),
    "cancelled": ("idle", "Cancelled."),
    "nothing": ("sad", "Nothing here can be downloaded."),
    "missing": ("sad", "Something I need is missing."),
}


class State(Enum):
    LOADING = auto()
    READY = auto()
    UNAVAILABLE = auto()
    QUEUED = auto()
    DOWNLOADING = auto()
    DONE = auto()


@dataclass
class Item:
    """One video row."""

    url: str
    title: str
    row: int
    duration: float | None = None
    playlist: str | None = None
    index: int | None = None  # position in its playlist
    count: int | None = None  # size of that playlist
    options: list[Quality] = field(default_factory=list)
    state: State = State.LOADING
    size: int = 0  # expected bytes for the chosen quality
    finished_files: int = 0  # bytes of streams already complete (video, then audio)
    current_file: int = 0  # bytes of the stream in progress
    saved_info: dict | None = field(default=None, repr=False)  # the lookup's answer, kept for the download
    saved_at: float = 0.0
    saved_info_failed: bool = False
    combo: QComboBox | None = field(default=None, repr=False)
    bar: GoldBar | None = field(default=None, repr=False)

    @property
    def received(self) -> int:
        return self.finished_files + self.current_file


@dataclass
class Running:
    """A yt-dlp download process and the output we have not parsed yet."""

    item: Item
    info_file: str = ""  # set when the download reuses the lookup's answer instead of asking again
    buffer: bytes = b""
    error: str = ""
    already_there: bool = False


def open_settings() -> QSettings:
    """The saved choices: folder, quality, theme, speed of the last download.

    They live wherever the system keeps such things (the registry on Windows, a
    plist on macOS, ~/.config on Linux). YTGRAB_SETTINGS names an .ini file to
    use instead, which is also how the tests stay away from real settings.
    """
    path = os.environ.get("YTGRAB_SETTINGS")
    if path:
        return QSettings(path, QSettings.Format.IniFormat)
    return QSettings("ytgrab", "ytgrab")


def personal_icon() -> Path | None:
    """Your own emblem, if you have put an icon.png in ytgrab's settings folder; it replaces the built-in one."""
    override = os.environ.get("YTGRAB_SETTINGS")
    if override:
        folder = Path(override).parent
    else:
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    icon = folder / "icon.png"
    return icon if icon.is_file() else None


def _in_cell(widget: QWidget, vertical: int) -> QWidget:
    """Wrap a widget so it keeps some air inside its table cell."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(8, vertical, 8, vertical)
    layout.addWidget(widget)
    return holder


def _dropdown() -> QComboBox:
    """A QComboBox whose list obeys the stylesheet; with Qt's default delegate the list ignores item rules."""
    combo = QComboBox()
    combo.setItemDelegate(QStyledItemDelegate(combo))
    return combo


def _caption(text: str) -> Text:
    """A small spaced-out label in capitals, for naming a control."""
    return Text(text.upper(), fonts.sans(11, QFont.Weight.DemiBold, 1.4), "muted")


class LinkRow(QWidget):
    """A link field with a tag saying what the link is."""

    changed = Signal()
    several_pasted = Signal(object, list)
    remove_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(CONTROL_HEIGHT)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("https://…")
        self.edit.setMinimumHeight(CONTROL_HEIGHT)
        self.badge = Pill()
        self.remove_button = LuxButton("", "quiet", small=True, glyph="close")
        self.remove_button.setAccessibleName("Remove this link")
        self.remove_button.setToolTip("Remove this link")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.badge)
        layout.addWidget(self.remove_button)

        self.edit.textChanged.connect(self._on_text)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        self._on_text("")

    def kind(self) -> UrlKind:
        return classify(self.edit.text())

    def link(self) -> str:
        return normalize(self.edit.text())

    def _on_text(self, text: str) -> None:
        links = split_links(text)
        if len(links) > 1:  # several links pasted at once: spread them over rows
            self.several_pasted.emit(self, links)
            return
        kind = classify(text)
        self.badge.set_kind(LINK_KINDS.get(kind, ""), kind.value)
        self.changed.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ytgrab")
        self.setAcceptDrops(True)

        self.settings = open_settings()
        fonts.load()
        theme.apply(QApplication.instance(), str(self.settings.value("theme", theme.AUTO)))

        self.items: list[Item] = []
        self.link_rows: list[LinkRow] = []
        self._mood = ""
        self._blocked = False  # a helper program is missing, so nothing can be fetched
        self._version_proc: QProcess | None = None
        self._height_before_log = 0  # window height to return to when the commands panel closes
        self._links_height = 0
        self._links_run = None
        self._revealed = False
        self._scratch = QTemporaryDir()  # holds the lookup answers handed back to yt-dlp; removed on exit

        # Info lookups: a bounded worker pool of yt-dlp processes.
        self._jobs: set[QProcess] = set()
        self._job_queue: deque[tuple[list[str], Callable[[bool, str, str], None]]] = deque()
        self._generation = 0  # bumped on every new listing, so late answers are dropped

        # Downloads: a second pool, sized by the "Videos at once" control.
        self._downloads: dict[QProcess, Running] = {}
        self._download_queue: deque[Item] = deque()
        self._batch: list[Item] = []
        self._cancelling = False
        self._meter = SpeedMeter()
        self._started_at = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        # No narrower than its contents need, so the body never has to scroll sideways on an ordinary screen.
        screen = self.screen().availableGeometry()
        needed = self.canvas.minimumSizeHint().width() + 16
        self.setMinimumSize(min(needed, screen.width()), min(640, screen.height() - WINDOW_FRAME_ALLOWANCE))
        self.resize(min(1240, screen.width() - 40), min(960, screen.height() - WINDOW_FRAME_ALLOWANCE))
        self._add_link_row()
        self._refresh_summary()
        self._refresh_free_space()
        self._check_tools()

    # ---------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # The commands being run, hidden until asked for from the footer
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log.setMaximumBlockCount(2000)
        self.log.setFixedHeight(LOG_HEIGHT)
        self.log.setVisible(False)

        links_panel = self._build_links_panel()
        folder_panel = self._build_folder_panel()
        videos_panel = self._build_videos_panel()
        top = QHBoxLayout()
        top.setSpacing(BODY_SPACING)
        top.addWidget(links_panel, 5)
        top.addWidget(folder_panel, 4)

        self.canvas = Canvas()
        self._body = QVBoxLayout(self.canvas)
        self._body.setContentsMargins(*BODY_MARGINS)
        self._body.setSpacing(BODY_SPACING)
        self._body.addLayout(top)
        self._body.addWidget(self._build_preferences())
        self._body.addWidget(videos_panel, 1)
        self._body.addWidget(self.log)
        self._panels = [links_panel, folder_panel, videos_panel]
        for panel in self._panels:
            self.canvas.add_panel(panel)

        # The body scrolls if the window is ever too small for it, so nothing is cut off on a small screen.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.canvas)

        outer.addWidget(self._build_header())
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_footer())

    def _build_header(self) -> HeaderBand:
        header = HeaderBand()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(BODY_MARGINS[0], 0, BODY_MARGINS[2], 1)
        layout.setSpacing(18)

        own_picture = personal_icon()
        self.emblem = Emblem(str(own_picture) if own_picture else None)
        title = Text("YTGRAB", fonts.display(27, 600, 8), "band_ink")
        # elided, so a narrow window shortens the tagline with an ellipsis instead of slicing it
        tagline = Text(
            "Videos and playlists, at the quality you choose", fonts.serif(15, italic=True), "band_gold", elide=True
        )
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addStretch(1)
        titles.addWidget(title)
        titles.addWidget(tagline)
        titles.addStretch(1)

        self.bubble = SpeechBubble()
        self.mascot = Mascot(76)
        layout.addWidget(self.emblem, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(titles, 1)
        layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _panel(self, numeral: str, title: str, hint: str = "") -> tuple[Panel, QVBoxLayout, QHBoxLayout]:
        """A numbered section: the panel, its content layout, and its heading row (for extras on the right)."""
        panel = Panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(PANEL_PADDING, 20, PANEL_PADDING, PANEL_PADDING)
        layout.setSpacing(16)

        heading = QHBoxLayout()
        heading.setSpacing(12)
        heading.addWidget(Medallion(numeral))
        heading.addWidget(Text(title.upper(), fonts.display(15, 600, 3.2), "ink"))
        heading.addSpacing(2)
        if hint:
            heading.addWidget(Text(hint, fonts.serif(15, italic=True), "muted", elide=True), 1)
        else:
            heading.addStretch(1)
        layout.addLayout(heading)
        return panel, layout, heading

    def _build_links_panel(self) -> Panel:
        panel, layout, heading = self._panel("I", "Links", "Paste or drop, as many as you like")
        self.add_button = LuxButton("+ Add another link", "secondary", small=True)
        self.add_button.setToolTip("Add one more video or playlist to download alongside the others")
        self.add_button.clicked.connect(lambda: self._add_link_row().edit.setFocus())
        heading.addWidget(self.add_button)

        self.rows_host = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        self.rows_scroll = QScrollArea()
        self.rows_scroll.setWidgetResizable(True)
        self.rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rows_scroll.setWidget(self.rows_host)
        self.rows_scroll.viewport().setAutoFillBackground(False)  # let the panel show through
        self.rows_host.setAutoFillBackground(False)
        layout.addWidget(self.rows_scroll)
        layout.addStretch(1)
        return panel

    def _build_folder_panel(self) -> Panel:
        panel, layout, heading = self._panel("II", "Download location")
        self.space_label = Text("", fonts.serif(15, italic=True), "muted")  # where the other panels have a hint
        heading.addWidget(self.space_label)

        default_folder = QDir.toNativeSeparators(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
        )
        self.folder_edit = QLineEdit(str(self.settings.value("folder", default_folder)))
        self.folder_edit.setMinimumHeight(CONTROL_HEIGHT)
        self.folder_edit.textChanged.connect(self._refresh_free_space)
        self.browse_button = LuxButton("Browse…", "secondary")
        self.browse_button.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.folder_edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)
        layout.addStretch(1)
        return panel

    def _build_preferences(self) -> RuledRow:
        self.quality_all = _dropdown()
        for height in STANDARD_HEIGHTS[:6]:
            self.quality_all.addItem(f"{height}p", height)
        saved_height = int(self.settings.value("height", DEFAULT_HEIGHT))
        self.quality_all.setCurrentIndex(max(self.quality_all.findData(saved_height), 0))
        self.quality_all.setFixedHeight(COMPACT_HEIGHT)
        self.quality_all.setMinimumWidth(100)
        self.quality_all.setToolTip("Applied to every video; a video without it gets the next one down")
        self.quality_all.currentIndexChanged.connect(self._apply_quality_to_all)

        self.upgrade_check = QCheckBox("1440p when under 300 MB")
        self.upgrade_check.setChecked(self.settings.value("upgrade_small", True, type=bool))
        self.upgrade_check.setToolTip("Takes the 1440p version of a video whenever it is smaller than 300 MB")
        self.upgrade_check.toggled.connect(self._apply_quality_to_all)

        self.parallel_spin = Stepper(1, 6, int(self.settings.value("parallel", DEFAULT_DOWNLOADS)))
        self.parallel_spin.setToolTip("How many videos download at the same time")

        self.next_button = LuxButton("Next: show videos", "primary")
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self.fetch)

        # Between two hairlines, and inset like a panel's contents, so the row shares the panels' left and right edges.
        strip = RuledRow()
        row = QHBoxLayout(strip)
        row.setContentsMargins(PANEL_PADDING, 14, PANEL_PADDING, 14)
        row.setSpacing(10)
        row.addWidget(_caption("Preferred quality"))
        row.addWidget(self.quality_all)
        row.addSpacing(6)
        row.addWidget(self.upgrade_check)
        row.addSpacing(14)
        row.addWidget(_caption("Videos at once"))
        row.addWidget(self.parallel_spin)
        row.addStretch(1)
        row.addWidget(self.next_button)
        return strip

    def _build_videos_panel(self) -> Panel:
        panel, layout, _heading = self._panel(
            "III", "Videos", "Every available quality with its size; tick the ones you want"
        )

        self.table = HintedTable(
            0, len(HEADERS), "Your videos will appear here", "Each with every quality on offer, and what it weighs"
        )
        self.table.setHorizontalHeaderLabels([name.upper() for name in HEADERS])
        self.table.setFont(fonts.sans(14, tabular=True))  # equal-width figures: lengths and sizes line up
        self.table.setItemDelegate(RowRule(self.table, loud=COL_TITLE))
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.viewport().setAutoFillBackground(False)  # let the panel show through
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setMinimumHeight(ROW_HEIGHT * 3)  # never squeezed below the header and two rows
        self.table.setWordWrap(False)  # long titles are cut with … and shown in full on hover
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setFixedHeight(40)
        # Per heading rather than in the stylesheet (which cannot space letters) or on the header
        # (whose own font the stylesheet resets): these then match the other small capitals.
        for column in range(len(HEADERS)):
            self.table.horizontalHeaderItem(column).setFont(fonts.sans(11, QFont.Weight.DemiBold, 1.4))
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        for column, width in ((COL_PICK, 70), (COL_LENGTH, 92), (COL_QUALITY, 204), (COL_SIZE, 104), (COL_PROGRESS, 184)):
            self.table.setColumnWidth(column, width)
        self.table.itemChanged.connect(lambda _item: self._refresh_summary())
        layout.addWidget(self.table, 1)

        self.summary = Text("", fonts.sans(14), "ink", elide=True)  # a long line is cut short, never widens the window
        self.download_button = LuxButton("Download", "primary")
        self.download_button.clicked.connect(self.start_downloads)
        self.cancel_button = LuxButton("Cancel", "secondary")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setVisible(False)  # one action shows at a time: Download, or Cancel while it runs
        self.cancel_button.clicked.connect(self.cancel_downloads)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.summary, 1)
        actions.addWidget(self.download_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

        # Overall progress and time left: shown from the first download on
        self.overall = OverallProgress()
        self.eta_label = self.overall.caption
        self.progress_box = self.overall
        self.progress_box.setVisible(False)
        layout.addWidget(self.progress_box)
        return panel

    def _build_footer(self) -> FooterBand:
        footer = FooterBand()
        self.tools_label = Text("", fonts.sans(12), "muted", elide=True)  # shortened rather than run into its neighbours
        self.theme_picker = ThemePicker()
        self.theme_picker.set_current(theme.current().key)
        self.theme_picker.chosen.connect(self.set_theme)
        self.menu_button = LuxButton(f"Add to {launcher.menu_name()}", "quiet", small=True)
        self.menu_button.setToolTip("Create a launcher, so ytgrab can be started like any other app")
        self.menu_button.clicked.connect(self._add_to_menu)
        self.log_toggle = LuxButton("Show commands", "quiet", small=True)
        self.log_toggle.setToolTip("Show the yt-dlp commands ytgrab runs for you")
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self._toggle_log)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(BODY_MARGINS[0], 0, BODY_MARGINS[2] - 10, 0)
        layout.setSpacing(6)
        layout.addWidget(self.tools_label, 1)
        layout.addSpacing(12)
        layout.addWidget(_caption("Theme"))
        layout.addSpacing(4)
        layout.addWidget(self.theme_picker)
        layout.addSpacing(16)
        layout.addWidget(self.menu_button)
        layout.addWidget(self.log_toggle)
        return footer

    # ---------------------------------------------------------- look and feel

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not self._revealed:
            self._revealed = True
            self._reveal()

    def _reveal(self) -> None:
        """As the window opens, the panels fade in one after another and settle upwards."""
        for order, panel in enumerate(self._panels):
            motion.fade_in(panel, 520, delay=110 * order, on_frame=self.canvas.update)
        left, top, right, bottom = BODY_MARGINS

        def settle(drop: float) -> None:
            self._body.setContentsMargins(left, top + round(drop), right, bottom - round(drop))

        motion.animate(self, 14.0, 0.0, 620, settle)

    def set_theme(self, key: str) -> None:
        """Switch to a theme chosen in the footer, and remember it."""
        self.settings.setValue("theme", key)
        self._restyle()

    def follow_system(self) -> None:
        """The system switched between light and dark: follow it, unless a theme was chosen by hand."""
        if str(self.settings.value("theme", theme.AUTO)) not in theme.THEMES:
            self._restyle()

    def _restyle(self) -> None:
        veil = None
        if motion.enabled() and self.isVisible():
            # A picture of the old look laid over the window and faded away, so the change is not a hard cut.
            veil = QLabel(self)
            veil.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            veil.setPixmap(self.grab())
            veil.setGeometry(self.rect())
            veil.show()
            veil.raise_()

        theme.apply(QApplication.instance(), str(self.settings.value("theme", theme.AUTO)))
        for label in self.findChildren(Text):
            label.retint()
        self.theme_picker.set_current(theme.current().key)
        self.update()

        if veil is not None:
            effect = QGraphicsOpacityEffect(veil)
            veil.setGraphicsEffect(effect)
            motion.animate(veil, 1.0, 0.0, 420, effect.setOpacity, on_done=veil.deleteLater)

    def _add_to_menu(self) -> None:
        try:
            where = launcher.install()
        except (OSError, KeyError, subprocess.SubprocessError) as error:
            dialogs.tell(self, "That did not work", f"ytgrab could not be added to the {launcher.menu_name()}.\n\n{error}", "sad")
            return
        dialogs.tell(self, "Added", f"ytgrab is now in your {launcher.menu_name()}.\n\n{where}", "happy")

    def _toggle_log(self, shown: bool) -> None:
        self.log_toggle.setText("Hide commands" if shown else "Show commands")
        resizable = not (self.isMaximized() or self.isFullScreen())
        if shown:
            # Make room for the panel instead of squeezing the table, as far as the screen allows.
            self._height_before_log = self.height()
            self.log.setVisible(True)
            if resizable:
                limit = self.screen().availableGeometry().height() - WINDOW_FRAME_ALLOWANCE
                wanted = self._height_before_log + LOG_HEIGHT + BODY_SPACING
                self.resize(self.width(), max(self._height_before_log, min(wanted, limit)))
        else:
            self.log.setVisible(False)
            height, self._height_before_log = self._height_before_log, 0
            if resizable and height:
                self.resize(self.width(), height)

    def _set_mood(self, name: str) -> None:
        if name != self._mood:
            self._mood = name
            mood, words = MOODS[name]
            self.mascot.set_mood(mood)
            self.bubble.setText(words)

    def _refresh_free_space(self) -> None:
        path = Path(self.folder_edit.text().strip() or ".").expanduser()
        while not path.exists() and path != path.parent:
            path = path.parent  # a folder that will be created: measure the drive it will land on
        try:
            self.space_label.setText(f"{human_size(shutil.disk_usage(path).free)} free")
        except OSError:
            self.space_label.clear()

    def _block(self, reason: str) -> None:
        """A helper program is unusable: say so and stop new listings."""
        self._blocked = True
        self.summary.setText(reason)
        self.next_button.setEnabled(False)
        self._set_mood("missing")

    def _check_tools(self) -> None:
        """Fill the footer with what was found, and block the app if something essential is missing."""
        runtime = tools.js_runtime()
        notes = [
            "ffmpeg ready" if tools.ffmpeg_path() else "ffmpeg missing",
            f"{runtime[0]} ready" if runtime else "no JavaScript runtime, so some qualities may be missing",
        ]
        self.tools_label.setText("  ·  ".join(["yt-dlp", *notes]))
        if not tools.ffmpeg_path():
            self._block("ffmpeg was not found. Run `python -m ytgrab --check` in a terminal for details.")

        proc = self._version_proc = self._spawn(ytdlp.version_cmd())

        def show_version(*_args) -> None:
            if not isValid(proc) or self._version_proc is not proc:  # window closed, or already handled
                return
            self._version_proc = None
            version = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace").strip()
            proc.deleteLater()
            if version:
                self.tools_label.setText("  ·  ".join([f"yt-dlp {version}", *notes]))
            else:
                self.tools_label.setText("  ·  ".join(["yt-dlp is not working", *notes]))
                self._block("yt-dlp could not be started. Run `python -m ytgrab --check` in a terminal for details.")

        proc.finished.connect(show_version)
        proc.errorOccurred.connect(
            lambda error: show_version() if error == QProcess.ProcessError.FailedToStart else None
        )
        proc.start(*self._split(ytdlp.version_cmd()))

    @staticmethod
    def _split(cmd: list[str]) -> tuple[str, list[str]]:
        return cmd[0], cmd[1:]

    # ----------------------------------------------------------------- links

    def _add_link_row(self, text: str = "") -> LinkRow:
        row = LinkRow()
        row.changed.connect(self._refresh_link_area)
        row.several_pasted.connect(self._spread_links)
        row.remove_requested.connect(self._remove_link_row)
        self.link_rows.append(row)
        self.rows_layout.addWidget(row)
        row.edit.setText(text)
        self._refresh_link_area()
        return row

    def _remove_link_row(self, row: LinkRow) -> None:
        if len(self.link_rows) == 1:
            row.edit.clear()
            return
        self.link_rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_link_area()

    def _spread_links(self, row: LinkRow, links: list[str]) -> None:
        row.edit.setText(links[0])
        self._add_links(links[1:])

    def _add_links(self, links: list[str]) -> None:
        for link in links:
            empty = next((row for row in self.link_rows if not row.edit.text().strip()), None)
            if empty:
                empty.edit.setText(link)
            else:
                self._add_link_row(link)

    def _refresh_link_area(self) -> None:
        """The link list grows with its rows, easing to the new height, then scrolls."""
        shown = min(len(self.link_rows), MAX_LINK_ROWS_SHOWN)
        height = CONTROL_HEIGHT * shown + self.rows_layout.spacing() * max(shown - 1, 0)
        if height == self._links_height:
            return
        start, self._links_height = self._links_height, height
        motion.stop(self._links_run)
        if start and self.isVisible():
            self._links_run = motion.animate(
                self.rows_scroll, start, height, 200, lambda value: self.rows_scroll.setFixedHeight(round(value))
            )
        else:
            self.rows_scroll.setFixedHeight(height)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        text = "\n".join(url.toString() for url in mime.urls()) if mime.hasUrls() else mime.text()
        self._add_links(split_links(text))
        event.acceptProposedAction()

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose where to save the videos", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(QDir.toNativeSeparators(folder))

    # ------------------------------------------------------- running yt-dlp

    def _spawn(self, cmd: list[str]) -> QProcess:
        proc = QProcess(self)
        env = QProcessEnvironment()
        for name, value in tools.child_environment().items():
            env.insert(name, value)
        proc.setProcessEnvironment(env)
        self.log.appendPlainText("$ " + tools.display_command(cmd))
        return proc

    @staticmethod
    def _stop(proc: QProcess) -> None:
        """End a yt-dlp process. Its partial files stay on disk either way, so the download can resume."""
        if tools.WINDOWS:
            proc.kill()  # Windows has no polite stop signal for a program without a window
        else:
            proc.terminate()

    def _queue_job(self, cmd: list[str], callback: Callable[[bool, str, str], None]) -> None:
        self._job_queue.append((cmd, callback))
        self._pump_jobs()

    def _pump_jobs(self) -> None:
        while self._job_queue and len(self._jobs) < FETCH_PARALLEL:
            cmd, callback = self._job_queue.popleft()
            proc = self._spawn(cmd)
            done = partial(self._job_done, proc, self._generation, callback)
            proc.finished.connect(
                lambda code, status, done=done: done(code == 0 and status == QProcess.ExitStatus.NormalExit)
            )
            proc.errorOccurred.connect(
                lambda error, done=done: done(False) if error == QProcess.ProcessError.FailedToStart else None
            )
            self._jobs.add(proc)
            proc.start(*self._split(cmd))
        self._refresh_summary()

    def _job_done(self, proc: QProcess, generation: int, callback, ok: bool) -> None:
        if proc not in self._jobs:
            return
        self._jobs.discard(proc)
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        proc.deleteLater()
        if generation == self._generation:  # else the user started a new listing meanwhile
            callback(ok, out, err)
        self._pump_jobs()

    @staticmethod
    def _error_line(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        errors = [line for line in lines if line.startswith("ERROR")]
        return (errors or lines or ["yt-dlp gave no details"])[-1]

    # ------------------------------------------------------ listing (Next)

    def fetch(self) -> None:
        links = list(dict.fromkeys(row.link() for row in self.link_rows if row.kind() in FETCHABLE))
        if not links:
            self.summary.setText("Add at least one video or playlist link first.")
            return

        self._generation += 1
        self._job_queue.clear()
        for proc in list(self._jobs):
            proc.kill()
        self.items.clear()
        self.table.setRowCount(0)
        self.overall.set_progress(0.0, "idle")
        self.eta_label.clear()
        self.progress_box.setVisible(False)

        for order, link in enumerate(links):
            if classify(link) is UrlKind.VIDEO:
                item = self._add_item(link, link, reveal=order)
                self._queue_job(ytdlp.info_cmd(link), partial(self._on_info, item))
            else:
                self._queue_job(ytdlp.list_cmd(link), partial(self._on_listing, link))

    def _on_listing(self, link: str, ok: bool, out: str, err: str) -> None:
        try:
            data = json.loads(out) if ok else None
        except json.JSONDecodeError:
            data = None
        if not data:
            self._mark_unavailable(self._add_item(link, link), self._error_line(err))
            return

        if data.get("_type") != "playlist":  # a non-YouTube link that turned out to be one video
            self._apply_info(self._add_item(link, link, reveal=0), data)
            return

        # Two-phase fetch: the listing above was cheap, now fill in formats per video.
        # Numbers are the true playlist positions, so files keep their order even if an entry is missing.
        entries = data.get("entries") or []
        unfold = len(entries) <= ROW_REVEAL_LIMIT
        for index, entry in enumerate(entries, start=1):
            if not entry:
                continue
            url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
            item = self._add_item(
                url,
                entry.get("title") or url,
                entry.get("duration"),
                data.get("title"),
                index,
                len(entries),
                reveal=index - 1 if unfold else None,
            )
            self._queue_job(ytdlp.info_cmd(url), partial(self._on_info, item))
        if not any(entries):
            self._mark_unavailable(self._add_item(link, data.get("title") or link), "This playlist has no videos")

    def _on_info(self, item: Item, ok: bool, out: str, err: str) -> None:
        try:
            info = json.loads(out) if ok else None
        except json.JSONDecodeError:
            info = None
        if info:
            self._apply_info(item, info)
        else:
            self._mark_unavailable(item, self._error_line(err))

    def _add_item(
        self, url, title, duration=None, playlist=None, index=None, count=None, reveal: int | None = None
    ) -> Item:
        """Add a table row. `reveal` (its place in the batch) makes the row unfold a moment after the one before."""
        row = self.table.rowCount()
        item = Item(url=url, title=title, row=row, duration=duration, playlist=playlist, index=index, count=count)
        self.items.append(item)

        self.table.blockSignals(True)
        self.table.insertRow(row)
        pick = QTableWidgetItem(str(row + 1))
        pick.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        pick.setCheckState(Qt.CheckState.Checked)
        self.table.setItem(row, COL_PICK, pick)
        self.table.setItem(row, COL_TITLE, QTableWidgetItem(title))
        self.table.setItem(row, COL_LENGTH, QTableWidgetItem(human_time(duration)))
        self.table.setItem(row, COL_SIZE, QTableWidgetItem("…"))
        self.table.blockSignals(False)

        item.combo = _dropdown()
        item.combo.addItem("Checking qualities…")
        item.combo.setEnabled(False)
        item.combo.currentIndexChanged.connect(partial(self._on_quality_changed, item))
        item.combo.setFixedHeight(COMPACT_HEIGHT)
        self.table.setCellWidget(row, COL_QUALITY, _in_cell(item.combo, (ROW_HEIGHT - COMPACT_HEIGHT) // 2))

        item.bar = GoldBar()
        self.table.setCellWidget(row, COL_PROGRESS, _in_cell(item.bar, (ROW_HEIGHT - GoldBar.HEIGHT) // 2))

        if reveal is not None and motion.enabled() and self.isVisible():

            def grow(value: float) -> None:
                if item.row < self.table.rowCount():
                    self.table.setRowHeight(item.row, round(value))

            motion.animate(item.bar, 0.0, ROW_HEIGHT, 280, grow, delay=30 * reveal)
        return item

    def _combo(self, item: Item) -> QComboBox:
        return item.combo

    def _bar(self, item: Item) -> GoldBar:
        return item.bar

    def _set_bar(
        self, item: Item, text: str, fraction: float | None = None, state: str = "idle", tip: str = ""
    ) -> None:
        """Update a row's progress bar. States: 'idle', 'active' (shimmers), 'done', 'failed'."""
        item.bar.set_progress(fraction, text, state)
        item.bar.setToolTip(tip)

    def _upgrade_small(self) -> bool:
        return self.upgrade_check.isChecked()

    def _apply_info(self, item: Item, info: dict) -> None:
        item.options = qualities(info)
        if not item.options:
            self._mark_unavailable(item, "No downloadable video found at this link")
            return
        item.title = info.get("title") or item.title
        item.duration = info.get("duration") or item.duration
        item.state = State.READY
        # Keep what the site just told us, so the download need not ask again.
        item.saved_info = ytdlp.slim_info(info, [option.format_spec for option in item.options])
        item.saved_at = time.monotonic()
        item.saved_info_failed = False

        self.table.item(item.row, COL_TITLE).setText(item.title)
        self.table.item(item.row, COL_TITLE).setToolTip(item.title)
        self.table.item(item.row, COL_LENGTH).setText(human_time(item.duration))

        combo = item.combo
        combo.blockSignals(True)
        combo.clear()
        for option in item.options:
            combo.addItem(option.describe())
        combo.setCurrentIndex(pick_default(item.options, self.quality_all.currentData(), self._upgrade_small()))
        combo.setEnabled(True)
        combo.blockSignals(False)
        self._on_quality_changed(item)

    def _mark_unavailable(self, item: Item, reason: str) -> None:
        item.state = State.UNAVAILABLE
        self.log.appendPlainText(f"{item.title}: {reason}")
        combo = item.combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Unavailable")
        combo.setEnabled(False)
        combo.blockSignals(False)
        self.table.blockSignals(True)
        self.table.item(item.row, COL_PICK).setCheckState(Qt.CheckState.Unchecked)
        self.table.item(item.row, COL_PICK).setFlags(Qt.ItemFlag.NoItemFlags)
        self.table.item(item.row, COL_SIZE).setText("–")
        self.table.blockSignals(False)
        self._set_bar(item, "Unavailable", 0.0, tip=reason)
        self._refresh_summary()

    def _chosen(self, item: Item) -> Quality:
        return item.options[max(item.combo.currentIndex(), 0)]

    def _on_quality_changed(self, item: Item, *_args) -> None:
        if item.state is State.READY:
            self.table.item(item.row, COL_SIZE).setText(human_size(self._chosen(item).size))
            self._refresh_summary()

    def _apply_quality_to_all(self, *_args) -> None:
        height = self.quality_all.currentData()
        self.settings.setValue("height", height)
        self.settings.setValue("upgrade_small", self._upgrade_small())
        for item in self.items:
            if item.state is State.READY:
                item.combo.setCurrentIndex(pick_default(item.options, height, self._upgrade_small()))

    def _is_checked(self, item: Item) -> bool:
        return self.table.item(item.row, COL_PICK).checkState() == Qt.CheckState.Checked

    def _refresh_summary(self) -> None:
        if self._batch or self._blocked:
            return  # the download line, or the missing-tool message, owns this line
        loading = len(self._jobs) + len(self._job_queue)
        picked = [item for item in self.items if item.state is State.READY and self._is_checked(item)]
        self.download_button.setEnabled(bool(picked) and not loading)

        if loading:
            self._set_mood("listing")
            self.summary.setText(f"Checking available qualities… {loading} lookups left")
            return
        if not self.items:
            self._set_mood("idle")
            self.summary.setText("Add links above, then press Next to see the videos, qualities and sizes.")
            return
        if picked:
            self._set_mood("ready")
        elif self._mood == "listing":  # the lookups ended and nothing can be downloaded
            self._set_mood("nothing")

        sizes = [self._chosen(item).size for item in picked]
        total = sum(size for size in sizes if size)
        text = f"{len(picked)} of {len(self.items)} videos selected  ·  {human_size(total)}"
        if None in sizes:
            text += " plus some of unknown size"
        last_speed = float(self.settings.value("last_speed", 0) or 0)
        if picked and last_speed:
            text += f"  ·  {human_eta(total / last_speed)} at your last speed of {human_size(last_speed)}/s"
        elif picked:
            text += "  ·  time left appears once the download starts"
        self.summary.setText(text)

    # -------------------------------------------------------------- download

    def start_downloads(self) -> None:
        folder = Path(self.folder_edit.text().strip() or ".").expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            dialogs.tell(self, "That folder can't be used", f"{folder}\n\n{error}", "sad")
            return
        self.settings.setValue("folder", str(folder))
        self.settings.setValue("parallel", self.parallel_spin.value())

        self._batch = [item for item in self.items if item.state is State.READY and self._is_checked(item)]
        if not self._batch:
            return
        for item in self._batch:
            item.state = State.QUEUED
            item.size = self._chosen(item).size or 0
            item.finished_files = item.current_file = 0
            self._set_bar(item, "Waiting", 0.0)

        self._download_queue = deque(self._batch)
        self._cancelling = False
        self._meter = SpeedMeter()
        self._started_at = time.monotonic()
        self.summary.setText(f"Downloading {len(self._batch)} of {len(self.items)} videos")
        self._set_mood("downloading")
        self.overall.set_progress(0.0, "active")
        self.progress_box.setVisible(True)
        self._set_busy(True)
        self._timer.start()
        self._pump_downloads()
        self._tick()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.next_button, self.download_button, self.quality_all, self.upgrade_check, self.parallel_spin,
            self.folder_edit, self.browse_button, self.add_button, self.rows_host,
        ):  # fmt: skip
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.download_button.setVisible(not busy)
        self.cancel_button.setVisible(busy)
        for item in self.items:
            if item.state in (State.READY, State.QUEUED):
                item.combo.setEnabled(not busy)

    def _pump_downloads(self) -> None:
        while self._download_queue and len(self._downloads) < self.parallel_spin.value():
            self._start_download(self._download_queue.popleft())
        if self._batch and not self._downloads and not self._download_queue:
            self._finish_batch()

    def _save_info_for(self, item: Item) -> str | None:
        """Write the lookup's answer to a file yt-dlp can read back, if it is still fresh enough to trust."""
        fresh = time.monotonic() - item.saved_at < SAVED_INFO_MAX_AGE
        if not item.saved_info or item.saved_info_failed or not fresh or not self._scratch.isValid():
            return None
        path = os.path.join(self._scratch.path(), f"video-{item.row}.json")
        try:
            Path(path).write_text(json.dumps(item.saved_info), encoding="utf-8")
        except OSError:
            return None
        return path

    def _start_download(self, item: Item) -> None:
        quality = self._chosen(item)
        template = ytdlp.output_template(
            self.settings.value("folder"), quality.label, item.playlist, item.index, item.count
        )
        # Videos running together share one budget of connections; a video on its own gets the most.
        sharing = min(self.parallel_spin.value(), len(self._downloads) + 1 + len(self._download_queue))
        info_file = self._save_info_for(item)
        cmd = ytdlp.download_cmd(item.url, quality.format_spec, template, ytdlp.fragments_for(sharing), info_file)

        proc = self._spawn(cmd)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(partial(self._on_download_output, proc))
        proc.finished.connect(
            lambda code, status, proc=proc: self._on_download_finished(
                proc, code == 0 and status == QProcess.ExitStatus.NormalExit
            )
        )
        proc.errorOccurred.connect(
            lambda error, proc=proc: self._on_download_finished(proc, False)
            if error == QProcess.ProcessError.FailedToStart
            else None
        )
        self._downloads[proc] = Running(item, info_file or "")
        item.state = State.DOWNLOADING
        self._set_bar(item, "Starting…", None, "active")
        if len(self._downloads) == 1:  # bring the working row into view, unless others are already being watched
            self.table.scrollToItem(self.table.item(item.row, COL_TITLE), QAbstractItemView.ScrollHint.EnsureVisible)
        proc.start(*self._split(cmd))

    def _on_download_output(self, proc: QProcess) -> None:
        running = self._downloads.get(proc)
        if running is None:
            return
        running.buffer += bytes(proc.readAllStandardOutput())
        *lines, running.buffer = running.buffer.split(b"\n")
        for raw in lines:
            self._on_download_line(running, raw.decode("utf-8", "replace").strip())

    def _on_download_line(self, running: Running, line: str) -> None:
        item = running.item
        progress = ytdlp.parse_progress(line)
        if progress:
            # Parallel fragments report out of order, so the counter can dip; keep the peak.
            item.current_file = max(item.current_file, progress.downloaded)
            # Trust the listed size; yt-dlp's running total for HLS swings too much to use.
            item.size = max(item.size, item.received)
            percent = min(int(item.received * 100 / item.size) if item.size else 0, 99)
            self._set_bar(item, f"{percent}%", percent / 100, "active")
        elif line.startswith("[download] Destination:"):  # next stream (video, then audio) begins
            item.finished_files += item.current_file
            item.current_file = 0
        elif line.startswith("[Merger]"):
            self._set_bar(item, "Merging…", 0.99, "active")
        elif "has already been downloaded" in line:
            running.already_there = True
        elif line.startswith("ERROR"):
            running.error = line
            self.log.appendPlainText(line)
        elif line.startswith("WARNING"):
            self.log.appendPlainText(line)

    def _on_download_finished(self, proc: QProcess, ok: bool) -> None:
        running = self._downloads.pop(proc, None)
        if running is None:
            return
        if running.buffer:
            self._on_download_line(running, running.buffer.decode("utf-8", "replace").strip())
        proc.deleteLater()
        item = running.item
        if running.info_file:
            try:
                os.remove(running.info_file)
            except OSError:
                pass

        if ok:
            item.state = State.DONE
            item.size = item.received  # the real figure replaces the estimate
            self._set_bar(item, "Already downloaded" if running.already_there else "Done", 1.0, "done")
            self.table.blockSignals(True)
            self.table.item(item.row, COL_PICK).setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.blockSignals(False)
            item.combo.setEnabled(False)
        elif running.info_file and not self._cancelling:
            # The saved answer did not work, most likely because its links have expired.
            # Ask the site again; whatever was already downloaded is kept and resumed.
            item.saved_info_failed = True
            item.finished_files = item.current_file = 0
            self.log.appendPlainText(f"{item.title}: the saved details no longer worked, looking the video up again")
            self._start_download(item)
            return
        else:
            item.state = State.READY  # can be tried again
            if self._cancelling:
                self._set_bar(item, "Cancelled")
            else:
                self._set_bar(item, "Failed", None, "failed", running.error or "yt-dlp stopped unexpectedly")
        self._pump_downloads()

    def cancel_downloads(self) -> None:
        self._cancelling = True
        for item in self._download_queue:
            item.state = State.READY
            self._set_bar(item, "Cancelled")
        self._download_queue.clear()
        for proc in list(self._downloads):
            self._stop(proc)
        self._pump_downloads()

    def _tick(self) -> None:
        if not self._batch:
            return
        received = sum(item.received for item in self._batch)
        self._meter.add(time.monotonic(), received)
        left = sum(max(item.size - item.received, 0) for item in self._batch if item.state is not State.DONE)
        total = received + left
        done = sum(item.state is State.DONE for item in self._batch)
        speed = self._meter.speed()

        self.overall.set_progress(received / total if total else 0.0)
        parts = [f"{done} of {len(self._batch)} done", f"{human_size(received)} of {human_size(total)}"]
        if speed:
            parts.append(f"{human_size(speed)}/s")
        parts.append(f"{human_eta(self._meter.eta(left))} left" if speed else "working out the time left…")
        self.eta_label.setText("  ·  ".join(parts))

    def _finish_batch(self) -> None:
        self._timer.stop()
        batch, self._batch = self._batch, []
        elapsed = time.monotonic() - self._started_at
        received = sum(item.received for item in batch)
        done = sum(item.state is State.DONE for item in batch)
        cancelled = self._cancelling

        if received >= MIN_BYTES_FOR_SPEED and elapsed > 0 and not cancelled:
            self.settings.setValue("last_speed", received / elapsed)
        if done == len(batch):
            self.overall.set_progress(1.0, "done")
        else:
            self.overall.set_progress(None, "idle")

        outcome = "Cancelled" if cancelled else "Finished"
        took = human_eta(elapsed).removeprefix("about ")
        self.eta_label.setText(
            f"{outcome}: {done} of {len(batch)} downloaded in {took}  ·  {human_size(received)}"
            f"  ·  saved to {self.settings.value('folder')}"
        )
        self._cancelling = False
        self._set_busy(False)
        self._refresh_summary()
        self._refresh_free_space()
        self._set_mood("cancelled" if cancelled else "done" if done == len(batch) else "failed")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._downloads:
            stop = dialogs.ask(
                self,
                "Stop the downloads?",
                "Downloads are still running. What has arrived so far is kept, so they can be resumed later.",
                confirm="Stop and quit",
                cancel="Keep downloading",
            )
            if not stop:
                event.ignore()
                return
        self._generation += 1
        self._job_queue.clear()
        self._download_queue.clear()
        self._batch = []
        side = [self._version_proc] if self._version_proc else []
        for proc in [*self._jobs, *self._downloads, *side]:
            proc.blockSignals(True)
            self._stop(proc)
            proc.waitForFinished(1500)
        event.accept()


def run_check() -> int:
    """Try each helper program once and report; the exit code says whether all of them work."""
    rows = tools.check()
    for name, works, detail in rows:
        print(f"{'ok  ' if works else 'FAIL'}  {name}: {detail}")
    return 0 if all(works for _name, works, _detail in rows) else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ytgrab", description="Download videos and playlists with yt-dlp.")
    parser.add_argument("--version", action="version", version=f"ytgrab {__version__}")
    parser.add_argument("--check", action="store_true", help="test yt-dlp, ffmpeg and the JavaScript runtime, then exit")
    parser.add_argument(
        "--add-to-menu", action="store_true", help=f"add ytgrab to the {launcher.menu_name()}, then exit"
    )
    options, qt_arguments = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if options.check:
        sys.exit(run_check())
    if options.add_to_menu:
        print(launcher.install())
        return

    if tools.WINDOWS:  # give the taskbar our own icon and grouping instead of Python's
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ytgrab.app")
        except (AttributeError, OSError):
            pass

    app = QApplication([sys.argv[0], *qt_arguments])
    app.setApplicationName("ytgrab")
    app.setDesktopFileName("ytgrab")  # Linux: ties the window to its launcher, so the dock shows the right icon
    icon = personal_icon() or theme.ICON_PATH
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()  # loads the fonts and applies the saved theme
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: window.follow_system())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
