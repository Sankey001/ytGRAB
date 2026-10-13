"""The window itself, driven without a display and without the network."""

import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QProcess, Qt, QTimer

from ytgrab import app as app_module
from ytgrab import motion, theme
from ytgrab.app import COL_PICK, COL_SIZE, MainWindow, Running, State, personal_icon
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
    return {
        "id": "abc",
        "title": title,
        "duration": 600,
        "formats": formats,
        "thumbnails": [{"url": "t"}],
        "automatic_captions": {"en": [{"url": "c"}]},
    }


@pytest.fixture
def window(qapp):
    window = MainWindow()
    window.show()
    yield window
    window.close()


def add(window: MainWindow, title: str, sizes: dict[int, int]):
    item = window._add_item("https://example.com/v", title)
    window._apply_info(item, info(title, sizes))
    return item


def spin(qapp, seconds: float) -> None:
    """Let Qt run for a moment, so timers and animations get their turn."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()


# ------------------------------------------------------------------ basics


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
    assert not window.progress_box.isVisible()


def test_pasting_several_links_spreads_them_over_rows(window):
    window.link_rows[0].edit.setText("https://youtu.be/aaa https://youtube.com/playlist?list=PL1 not-a-link")
    assert [(row.edit.text(), row.badge.text()) for row in window.link_rows] == [
        ("https://youtu.be/aaa", "Video"),
        ("https://youtube.com/playlist?list=PL1", "Playlist"),
    ]


def test_the_link_tag_only_takes_room_when_there_is_a_link(window):
    row = window.link_rows[0]
    assert not row.badge.isVisible()
    row.edit.setText("https://youtu.be/aaa")
    assert row.badge.isVisible() and row.badge.kind == "video" and row.badge.width() == row.badge.WIDTH
    row.edit.setText("not a link")
    assert row.badge.kind == "invalid"
    row.edit.clear()
    assert not row.badge.isVisible()


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
    assert item.bar.text() == "Unavailable" and item.bar.state() == "idle"
    assert not window.download_button.isEnabled()


def test_commands_panel_opens_and_closes(window):
    window.log_toggle.setChecked(True)
    assert window.log.isVisible()
    window.log_toggle.setChecked(False)
    assert not window.log.isVisible()


def test_videos_at_once_keeps_to_its_range(window):
    window.parallel_spin.setValue(99)
    assert window.parallel_spin.value() == 6 and not window.parallel_spin.plus.isEnabled()
    window.parallel_spin.setValue(0)
    assert window.parallel_spin.value() == 1 and not window.parallel_spin.minus.isEnabled()
    window.parallel_spin.plus.click()
    assert window.parallel_spin.value() == 2


# ------------------------------------------------------------------- themes


def test_theme_follows_the_environment_then_the_saved_choice(qapp, monkeypatch):
    for flavour, key in (("dark", "heritage"), ("light", "ivory"), ("midnight", "midnight")):
        monkeypatch.setenv("YTGRAB_THEME", flavour)
        assert theme.apply(qapp).key == key
    assert theme.apply(qapp, saved="bordeaux").key == "midnight"  # the environment wins for this run

    monkeypatch.delenv("YTGRAB_THEME")
    assert theme.apply(qapp, saved="bordeaux").key == "bordeaux"
    assert theme.apply(qapp, saved="no-such-theme").key in (theme.DEFAULT_DARK, theme.DEFAULT_LIGHT)


def test_picking_a_theme_restyles_the_window_and_is_remembered(window, isolated_settings):
    for key in theme.THEMES:
        window.theme_picker.swatches[key].click()
        assert theme.current().key == key
        assert window.settings.value("theme") == key
        assert window.theme_picker.swatches[key].isChecked()
        assert not window.grab().isNull()
    window.settings.sync()

    reopened = MainWindow()  # a new window starts in the theme that was chosen last
    assert theme.current().key == list(theme.THEMES)[-1]
    reopened.close()


def test_the_mascot_draws_in_every_mood_and_theme(qapp):
    mascot = Mascot(96)
    for key in theme.THEMES:
        theme.select(key)
        for mood in MOODS:
            mascot.set_mood(mood)
            assert mascot.mood() == mood
            image = mascot.grab().toImage()
            assert any(image.pixelColor(x, 48).alpha() for x in range(96)), (key, mood)
    mascot.set_mood("idle")  # stops the animation timer


def test_your_own_emblem_replaces_the_built_in_one(isolated_settings):
    assert personal_icon() is None
    (isolated_settings.parent / "icon.png").write_bytes(theme.ICON_PATH.read_bytes())
    assert personal_icon() == isolated_settings.parent / "icon.png"


# ---------------------------------------------------------------- downloads


def test_progress_shows_on_the_row_and_overall(window):
    item = add(window, "one", {1080: 100})
    running = Running(item)
    item.size = 120 * MB

    window._on_download_line(running, f"YTGRAB|{30 * MB}|NA|NA|NA")
    assert item.bar.text() == "25%" and item.bar.state() == "active" and item.bar.fraction() == 0.25

    window._on_download_line(running, "[download] Destination: sound.m4a")  # the second stream starts from zero
    window._on_download_line(running, f"YTGRAB|{30 * MB}|NA|NA|NA")
    assert item.received == 60 * MB and item.bar.text() == "50%"

    window._on_download_line(running, "[Merger] Merging formats into x.mp4")
    assert item.bar.text() == "Merging…"

    window._batch = [item]
    window._tick()
    assert window.overall.fraction() == 0.5 and window.overall.figure.text() == "50%"
    window._batch = []


def test_the_lookup_answer_is_kept_slim_for_the_download(window):
    item = add(window, "one", {1440: 900, 1080: 400})
    assert {fmt["format_id"] for fmt in item.saved_info["formats"]} == {"a", "1440", "1080"}
    assert "thumbnails" not in item.saved_info and "automatic_captions" not in item.saved_info
    assert item.saved_info["title"] == "one"

    path = window._save_info_for(item)
    assert json.loads(Path(path).read_text(encoding="utf-8"))["id"] == "abc"

    item.saved_at -= app_module.SAVED_INFO_MAX_AGE + 1  # too old to trust: its links will have expired
    assert window._save_info_for(item) is None


def test_a_download_that_fails_on_the_saved_answer_is_retried_by_link(window, tmp_path, monkeypatch):
    item = add(window, "one", {1080: 100})
    item.state = State.DOWNLOADING
    saved = tmp_path / "video.json"
    saved.write_text("{}", encoding="utf-8")
    retried = []
    monkeypatch.setattr(window, "_start_download", retried.append)

    first = QProcess(window)
    window._downloads[first] = Running(item, str(saved))
    window._on_download_finished(first, False)
    assert retried == [item] and item.saved_info_failed and not saved.exists()
    assert window._save_info_for(item) is None  # the next attempt goes by link

    second = QProcess(window)  # by link this time: a failure now is final
    window._downloads[second] = Running(item)
    window._on_download_finished(second, False)
    assert retried == [item] and item.state is State.READY
    assert item.bar.text() == "Failed" and item.bar.state() == "failed"


def test_videos_running_together_share_the_connection_budget(window, monkeypatch):
    commands = []
    monkeypatch.setattr(QProcess, "start", lambda self, *args: commands.append(args[1]))  # never really start yt-dlp
    for name in ("one", "two", "three", "four"):
        add(window, name, {1080: 100})
    window.folder_edit.setText(str(Path(window.settings.fileName()).parent / "videos"))
    window.parallel_spin.setValue(3)

    window.start_downloads()
    fragments = [int(args[args.index("--concurrent-fragments") + 1]) for args in commands if "--format" in args]
    assert fragments == [13, 13, 13]  # three at once, with a fourth waiting
    assert all("--load-info-json" in args for args in commands if "--format" in args)
    assert window.progress_box.isVisible() and window.cancel_button.isEnabled()
    assert window.cancel_button.isVisible() and not window.download_button.isVisible()  # one action at a time

    window.cancel_downloads()
    for proc in list(window._downloads):  # the pretend processes never finish by themselves
        window._on_download_finished(proc, False)
    assert window._mood == "cancelled" and window.next_button.isEnabled()
    assert window.download_button.isVisible() and not window.cancel_button.isVisible()


def test_closing_mid_download_asks_first(window, qapp):
    """The window's own dialog puts the question; each answer does what it says."""
    item = add(window, "one", {1080: 100})
    process = QProcess(window)
    window._downloads[process] = Running(item)

    def answer(accept: bool) -> None:
        dialog = qapp.activeModalWidget()
        assert dialog.cancel_button is not None and "resumed" in dialog.message.text()
        (dialog.confirm_button if accept else dialog.cancel_button).click()

    QTimer.singleShot(0, lambda: answer(False))
    assert not window.close() and window.isVisible()  # "Keep downloading"
    QTimer.singleShot(0, lambda: answer(True))
    assert window.close() and not window.isVisible()  # "Stop and quit"


def test_notes_wrap_long_paths_and_take_one_button(qapp):
    from ytgrab import dialogs

    note = dialogs.LuxDialog(None, "Added", "ytgrab is now in your menu.\n\n/a/very/long/path/without/any/spaces/in/it", mood="happy")
    assert note.cancel_button is None and dialogs.ZERO_WIDTH_SPACE in note.message.text()
    note.show()
    assert not note.grab().isNull() and note.width() < 640
    note.confirm_button.click()
    assert note.result() == dialogs.QDialog.DialogCode.Accepted


# ------------------------------------------------------------------- motion


def test_everything_still_works_with_animation_on(qapp):
    """Runs the animated paths for real: the opening reveal, unfolding rows, shimmer, a theme change."""
    motion.set_enabled(True)
    try:
        window = MainWindow()
        window.show()
        spin(qapp, 0.25)
        window.link_rows[0].edit.setText("https://youtu.be/aaa")
        first = window._add_item("https://example.com/1", "one", reveal=0)
        second = window._add_item("https://example.com/2", "two", reveal=1)
        window._apply_info(first, info("one", {1080: 100}))
        window._set_bar(first, "40%", 0.4, "active")
        window._set_bar(second, "Done", 1.0, "done")
        window.progress_box.setVisible(True)
        window.overall.set_progress(0.3, "active")
        window._set_mood("downloading")
        spin(qapp, 0.45)
        window.theme_picker.swatches["ivory"].click()
        window.log_toggle.setChecked(True)
        spin(qapp, 0.6)

        assert theme.current().key == "ivory"
        assert window.table.rowHeight(second.row) == app_module.ROW_HEIGHT  # the rows finished unfolding
        assert window.bubble._shown == window.bubble.text() == "Downloading…"  # the new words faded fully in
        assert window.bubble._ink == 1.0
        assert 0.0 < first.bar._shown <= 0.4
        assert not window.grab().isNull()
        window.close()
    finally:
        motion.set_enabled(False)
