import os

from ytgrab import tools
from ytgrab.eta import SpeedMeter
from ytgrab.ytdlp import (
    PROGRESS_TAG,
    Progress,
    download_cmd,
    fragments_for,
    info_cmd,
    number_prefix,
    output_template,
    parse_progress,
    safe_name,
    slim_info,
)


def test_speed_needs_two_samples_then_averages_the_window():
    meter = SpeedMeter(window=10)
    assert meter.speed() is None
    meter.add(0, 0)
    assert meter.speed() is None
    meter.add(5, 5000)
    assert meter.speed() == 1000
    assert meter.eta(20_000) == 20


def test_old_samples_fall_out_of_the_window():
    meter = SpeedMeter(window=10)
    meter.add(0, 0)  # slow start...
    meter.add(10, 1000)
    meter.add(20, 101_000)  # ...then fast
    meter.add(25, 151_000)
    assert meter.speed() == 10_000  # only the last 10 s (plus one sample) count


def test_stalled_download_has_no_eta():
    meter = SpeedMeter()
    meter.add(0, 500)
    meter.add(5, 500)
    assert meter.eta(1000) is None


def test_parse_progress():
    assert parse_progress(f"{PROGRESS_TAG}|1024|4096|NA|512.5") == Progress(1024, 4096, 512.5)
    assert parse_progress(f"{PROGRESS_TAG}|1024|NA|8192.7|NA") == Progress(1024, 8192, None)
    assert parse_progress(f"{PROGRESS_TAG}|NA|NA|NA|NA") is None
    assert parse_progress("[download] Destination: a.mp4") is None


# Paths are built with os.path.join so the expectations hold with either kind of separator.


def test_output_template_for_single_video_and_playlist():
    folder = os.path.join("data", "vids")
    assert output_template(folder, "1080p") == os.path.join(folder, "%(title)s (1080p).%(ext)s")

    percent = os.path.join("data", "100% vids")
    assert output_template(percent, "720p", "CS329A: Agents | Part?", 3) == os.path.join(
        "data", "100%% vids", "CS329A_ Agents _ Part_", "03 - %(title)s (720p).%(ext)s"
    )


def test_playlist_numbers_are_padded_to_the_playlist_size():
    assert number_prefix(3, 9) == "03 - "  # at least two digits
    assert number_prefix(3, 45) == "03 - "
    assert number_prefix(3, 250) == "003 - "
    assert number_prefix(120, 250) == "120 - "
    assert number_prefix(7) == "07 - "
    assert output_template("v", "1080p", "Course", 3, 250) == os.path.join(
        "v", "Course", "003 - %(title)s (1080p).%(ext)s"
    )


def test_padded_names_sort_in_playlist_order():
    names = [number_prefix(index, 120) + "x" for index in range(1, 121)]
    assert sorted(names) == names


def test_safe_name_is_valid_on_every_system():
    assert safe_name(" ... ") == "Playlist"
    assert safe_name('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"
    assert safe_name("trailing dot. ") == "trailing dot"
    assert safe_name("CON") == "_CON"  # reserved device names on Windows
    assert safe_name("aux.notes") == "_aux.notes"
    assert safe_name("console") == "console"


def test_download_cmd_passes_the_exact_format_and_single_video_flag():
    cmd = download_cmd("https://youtu.be/x", "270+234", os.path.join("out", "%(title)s.%(ext)s"))
    assert cmd[cmd.index("--format") + 1] == "270+234"
    assert "--no-playlist" in cmd
    assert cmd[-1] == "https://youtu.be/x"


def test_commands_do_not_depend_on_the_machine_they_run_on():
    cmd = download_cmd("https://youtu.be/x", "18", "out.%(ext)s")
    assert cmd[: len(tools.ytdlp_command())] == tools.ytdlp_command()
    assert "--ignore-config" in cmd  # a user's own yt-dlp settings must not change the result
    assert cmd[cmd.index("--ffmpeg-location") + 1] == tools.ffmpeg_path()

    name, path = tools.js_runtime()
    for built in (cmd, info_cmd("https://youtu.be/x")):
        assert built[built.index("--js-runtimes") + 1] == f"{name}:{path}"


def test_fragment_budget_is_shared_between_videos():
    assert fragments_for(1) == 32  # a video on its own gets the most
    assert [fragments_for(n) for n in (2, 3, 4, 5, 6)] == [20, 13, 10, 8, 6]
    assert fragments_for(40) == 6 and fragments_for(0) == 32  # never below the floor, never above the cap
    assert all(fragments_for(n) * n <= 40 for n in range(2, 7))

    cmd = download_cmd("https://youtu.be/x", "18", "out.%(ext)s", fragments=13)
    assert cmd[cmd.index("--concurrent-fragments") + 1] == "13"


def test_download_can_reuse_a_saved_lookup_instead_of_the_link():
    by_link = download_cmd("https://youtu.be/x", "18", "out.%(ext)s")
    from_file = download_cmd("https://youtu.be/x", "18", "out.%(ext)s", info_file="saved.json")
    assert by_link[-1] == "https://youtu.be/x" and "--load-info-json" not in by_link
    assert from_file[-2:] == ["--load-info-json", "saved.json"] and "https://youtu.be/x" not in from_file


def test_slim_info_keeps_only_what_a_download_reads():
    info = {
        "id": "abc",
        "title": "A talk",
        "duration": 60,
        "webpage_url": "https://youtu.be/abc",
        "formats": [{"format_id": name, "url": name} for name in ("18", "137", "270", "234-20", "140")],
        "thumbnails": [1, 2, 3],
        "automatic_captions": {"en": []},
        "subtitles": {},
        "heatmap": [],
        "requested_formats": [{"format_id": "137"}],
    }
    slim = slim_info(info, ["270+234-20", "18"])
    assert [fmt["format_id"] for fmt in slim["formats"]] == ["18", "270", "234-20"]
    assert set(slim) == {"id", "title", "duration", "webpage_url", "formats"}
    assert len(info["formats"]) == 5  # the original is left alone
