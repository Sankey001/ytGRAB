"""The themes and the custom-drawn widgets."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF

from ytgrab import fonts, theme
from ytgrab.mascot import SpeechBubble
from ytgrab.widgets import (
    Figure,
    GoldBar,
    HintedTable,
    LuxButton,
    OverallProgress,
    Pill,
    RuledRow,
    Stepper,
    ThemePicker,
)


@pytest.fixture(autouse=True)
def heritage(qapp):
    theme.apply(qapp, "heritage")


def test_mixing_colours():
    assert theme.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert theme.mix("#102030", "#102030", 0.7) == "#102030"
    assert theme.lighten("#000000", 1.0) == "#ffffff" and theme.darken("#ffffff", 1.0) == "#000000"


def test_every_theme_is_complete_and_readable(qapp):
    def brightness(color: str) -> float:
        red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
        return 0.299 * red + 0.587 * green + 0.114 * blue

    assert theme.DEFAULT_DARK in theme.THEMES and theme.DEFAULT_LIGHT in theme.THEMES
    for key, candidate in theme.THEMES.items():
        assert candidate.key == key and candidate.name
        assert theme.apply(qapp, key) is candidate and theme.current() is candidate  # the stylesheet builds
        # text must stand well clear of what it sits on, and the band stays deep in every theme
        assert abs(brightness(candidate.ink) - brightness(candidate.surface)) > 140, key
        assert abs(brightness(candidate.on_accent) - brightness(candidate.accent)) > 110, key
        assert brightness(candidate.band) < 60, key
        assert (brightness(candidate.base) < 128) == candidate.dark, key


def test_bundled_fonts_load_and_their_weight_axis_changes_the_letters(qapp):
    fonts.load()
    sample = "DOWNLOAD LOCATION"
    light = QFontMetricsF(fonts.display(24, 400)).horizontalAdvance(sample)
    heavy = QFontMetricsF(fonts.display(24, 800)).horizontalAdvance(sample)
    assert heavy > light  # a real heavier cut is wider; a smeared regular one is not
    assert fonts.serif(20, italic=True).italic()
    for licence in ("OFL-Cinzel.txt", "OFL-PlayfairDisplay.txt"):
        assert "SIL Open Font License" in (fonts.FONT_DIR / licence).read_text(encoding="utf-8")


def test_progress_bar_eases_forward_and_resets_at_once(qapp):
    bar = GoldBar()
    bar.resize(180, 24)
    bar.set_progress(0.4, "40%", "active")
    assert (bar.fraction(), bar.text(), bar.state()) == (0.4, "40%", "active")
    bar.set_progress(1.7)
    assert bar.fraction() == 1.0  # kept within 0..1
    bar.set_progress(0.0, "Waiting", "idle")
    assert bar._shown == 0.0 and bar.state() == "idle"
    for state in ("idle", "active", "done", "failed"):
        bar.set_progress(0.6, state.title(), state)
        assert not bar.grab().isNull()


def test_overall_progress_counts_up_with_its_bar(qapp):
    overall = OverallProgress()
    overall.resize(600, 60)
    overall.set_progress(0.437, "active")
    assert overall.figure.text() == "43%" and overall.fraction() == 0.437
    overall.set_progress(1.0, "done")
    assert overall.figure.text() == "100%"
    assert Figure().text() == "0%"
    assert not overall.grab().isNull()


def test_buttons_size_to_their_label_and_draw_in_every_kind(qapp):
    primary = LuxButton("Download", "primary")
    assert primary.sizeHint().width() > LuxButton("Go", "primary").sizeHint().width()
    assert LuxButton("x", "quiet", small=True, glyph="close").sizeHint().width() == 32
    for kind in ("primary", "secondary", "quiet"):
        for enabled in (True, False):
            button = LuxButton("Label", kind)
            button.setEnabled(enabled)
            button.resize(button.sizeHint())
            assert not button.grab().isNull()
    clicks = []
    primary.clicked.connect(lambda: clicks.append(1))
    primary.click()
    assert clicks == [1]


def test_stepper_reports_changes_once(qapp):
    stepper = Stepper(1, 6, 3)
    seen = []
    stepper.valueChanged.connect(seen.append)
    stepper.setValue(3)
    stepper.setValue(5)
    stepper.minus.click()
    assert seen == [5, 4] and stepper.value() == 4


def test_theme_picker_offers_every_theme(qapp):
    picker = ThemePicker()
    chosen = []
    picker.chosen.connect(chosen.append)
    assert list(picker.swatches) == list(theme.THEMES)
    picker.swatches["ivory"].click()
    assert chosen == ["ivory"] and picker.swatches["ivory"].isChecked()
    picker.set_current("midnight")
    assert picker.swatches["midnight"].isChecked() and not picker.swatches["ivory"].isChecked()


def test_speech_bubble_fits_its_words(qapp):
    bubble = SpeechBubble()
    bubble.setText("Hello")
    short = bubble.sizeHint().width()
    bubble.setText("A considerably longer thing to say")
    assert bubble.text() == "A considerably longer thing to say" and bubble.sizeHint().width() > short


def test_small_pieces_draw(qapp):
    pill = Pill()
    pill.set_kind("playlist", "Playlist")
    assert pill.text() == "Playlist" and not pill.isHidden()
    pill.set_kind("", "")
    assert pill.isHidden()

    table = HintedTable(0, 2, "Your videos will appear here", "Add a link")
    table.resize(400, 200)
    assert not table.grab().isNull()
    table.insertRow(0)
    assert not table.grab().isNull()
    assert table.focusPolicy() != Qt.FocusPolicy.NoFocus  # a plain table keeps Qt's defaults until the app changes them


def test_a_row_with_nothing_to_report_draws_nothing(qapp):
    bar = GoldBar()
    bar.resize(180, GoldBar.HEIGHT)
    blank = bar.grab().toImage()
    bar.set_progress(0.5, "50%", "active")
    assert bar.grab().toImage() != blank
    bar.set_progress(0.0, "", "idle")
    assert bar.grab().toImage() == blank


def test_the_table_fades_only_while_rows_wait_below(qapp):
    table = HintedTable(0, 1, "Nothing yet", "Add a link")
    table.resize(300, 160)
    table.show()
    assert table._fade.isHidden()
    for _row in range(12):
        table.insertRow(table.rowCount())
    qapp.processEvents()
    assert not table._fade.isHidden()
    table.verticalScrollBar().setValue(table.verticalScrollBar().maximum())
    assert table._fade.isHidden()
    table.close()


def test_sizes_come_from_one_scale(qapp):
    assert LuxButton("Download", "primary").sizeHint().height() == theme.CONTROL_HEIGHT
    assert LuxButton("Add", "secondary", small=True).sizeHint().height() == theme.COMPACT_HEIGHT
    row = RuledRow()
    row.resize(400, 60)
    assert not row.grab().isNull()
