"""The window itself, driven without a display and without the network."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from ytgrab import theme
from ytgrab.app import COL_PICK, COL_SIZE, MainWindow, State
from ytgrab.mascot import MOODS, Mascot

MB = 1024 * 1024


def info(title: str, sizes: dict[int, int]) -> dict:
    """What yt-dlp would report for a video offering these heights (sizes in MB, plus 20 MB of sound)."""
    formats = [{"format_id": "a", "vcodec": "none", "acodec": "mp4a.40.2", "filesize": 20 * MB}]
    for height, size in sizes.items():
        formats.append(
            {
                "format_id": str(height),
                "height": height,
                "width": height * 16 // 9,
                "vcodec": "avc1.64",
                "acodec": "none",
                "filesize": size * MB,
                "fps": 30,
            }
        )
    return {"title": title, "duration": 600, "formats": formats}


@pytest.fixture
def window(qapp):
    theme.apply(qapp)
    window = MainWindow()
    window.show()
    yield window
    window.close()


def add(window: MainWindow, title: str, sizes: dict[int, int]):
    item = window._add_item("https://example.com/v", title)
    window._apply_info(item, info(title, sizes))
    return item


def test_settings_go_to_the_throwaway_file_not_the_real_one(window, isolated_settings):
    """Guards the test setup itself: a leak here would overwrite a real user's choices."""
    assert Path(window.settings.fileName()) == isolated_settings
    window.upgrade_check.setChecked(False)
    window.settings.sync()
    assert "upgrade_small=false" in isolated_settings.read_text(encoding="utf-8")


def test_starts_empty_and_ready_for_a_link(window):
    assert len(window.link_rows) == 1
    assert not window.download_button.isEnabled()
    assert window._mood == "idle" and window.bubble.text()
    assert not window._blocked, window.summary.text()


def test_pasting_several_links_spreads_them_over_rows(window):
    window.link_rows[0].edit.setText("https://youtu.be/aaa https://youtube.com/playlist?list=PL1 not-a-link")
    assert [(row.edit.text(), row.badge.text()) for row in window.link_rows] == [
        ("https://youtu.be/aaa", "Video"),
        ("https://youtube.com/playlist?list=PL1", "Playlist"),
    ]


def test_small_1440p_is_preselected_and_the_tick_box_turns_that_off(window):
    small = add(window, "small", {1440: 200, 1080: 150, 720: 60})
    large = add(window, "large", {1440: 900, 1080: 400, 720: 150})
    assert small.combo.currentText().startswith("1440p") and large.combo.currentText().startswith("1080p")
    assert window.table.item(small.row, COL_SIZE).text() == "220 MB"

    window.upgrade_check.setChecked(False)
    assert small.combo.currentText().startswith("1080p")
    assert window.download_button.isEnabled() and window._mood == "ready"


def test_a_video_that_cannot_be_fetched_is_shown_but_not_selected(window):
    item = window._add_item("https://example.com/gone", "gone")
    window._mark_unavailable(item, "ERROR: Private video")
    assert item.state is State.UNAVAILABLE
    assert window.table.item(item.row, COL_PICK).checkState() == Qt.CheckState.Unchecked
    assert not window.download_button.isEnabled()


def test_commands_panel_opens_and_closes(window):
    window.log_toggle.setChecked(True)
    assert window.log.isVisible()
    window.log_toggle.setChecked(False)
    assert not window.log.isVisible()


def test_both_colour_flavours_apply(qapp, monkeypatch):
    for flavour, colours in (("dark", theme.DARK), ("light", theme.LIGHT)):
        monkeypatch.setenv("YTGRAB_THEME", flavour)
        assert theme.apply(qapp) is colours


def test_the_mascot_draws_in_every_mood(qapp):
    mascot = Mascot(96)
    for mood in MOODS:
        mascot.set_mood(mood)
        assert mascot.mood() == mood
        image = mascot.grab().toImage()
        assert any(image.pixelColor(x, 48).alpha() for x in range(96)), mood
    mascot.set_mood("idle")  # stops the animation timer
