from ytgrab.formats import Quality, human_eta, human_size, human_time, pick_default, qualities

MB = 1024 * 1024


def video(format_id, height, protocol="https", vcodec="avc1.640028", size=None, tbr=None, width=None, fps=30, **extra):
    return {
        **extra,
        "format_id": format_id,
        "height": height,
        "width": width or height * 16 // 9,
        "protocol": protocol,
        "vcodec": vcodec,
        "acodec": "none",
        "filesize": size,
        "tbr": tbr,
        "fps": fps,
    }


def audio(format_id, protocol="https", size=None, abr=128, **extra):
    return {
        "format_id": format_id,
        "protocol": protocol,
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "filesize": size,
        "abr": abr,
        **extra,
    }


def test_one_entry_per_height_best_first_with_audio_added():
    info = {
        "duration": 100,
        "formats": [
            video("136", 720, size=50 * MB),
            video("137", 1080, size=100 * MB),
            audio("140", size=10 * MB),
            {"format_id": "sb0", "vcodec": "none", "acodec": "none", "height": 90},  # storyboard
        ],
    }
    assert qualities(info) == [
        Quality(1080, "1080p", "137+140", 110 * MB),
        Quality(720, "720p", "136+140", 60 * MB),
    ]


def hls_audio(format_id, **extra):
    # what YouTube really sends: codec unknown (null), no bitrate, no size
    return {"format_id": format_id, "protocol": "m3u8_native", "vcodec": "none", "acodec": None, **extra}


def test_hls_h264_is_preferred_and_sized_from_its_https_twin():
    info = {
        "duration": 100,
        "formats": [
            hls_audio("233", language="en"),
            hls_audio("234", language="en"),
            audio("140", size=10 * MB, language="en"),
            audio("140-0", size=99 * MB, language="hi"),
            video("137", 1080, size=100 * MB, tbr=700),
            video("248", 1080, vcodec="vp9", size=160 * MB),
            video("614", 1080, protocol="m3u8_native", vcodec="vp09.00.40.08", tbr=3000),
            video("270", 1080, protocol="m3u8_native", tbr=1900),  # peak bitrate, far above the real 700
            video("616", 1080, protocol="m3u8_native", vcodec="vp09.00.40.08", tbr=9000, format_note="Premium"),
        ],
    }
    (only,) = qualities(info)
    assert only.format_spec == "270+234"  # 234 over 233: listed later, so better
    assert only.size == 110 * MB  # sizes of 137 and the English 140


def test_size_falls_back_to_bitrate_when_no_twin_has_a_size():
    info = {"duration": 100, "formats": [video("270", 1080, protocol="m3u8_native", tbr=4000), hls_audio("234")]}
    (only,) = qualities(info)
    assert only.format_spec == "270+234"
    # audio size is unknowable here, so the video's bitrate estimate stands alone
    assert only.size == 4000 * 1000 // 8 * 100


def test_bitrate_estimate_for_a_video_with_sound():
    info = {"duration": 100, "formats": [{"format_id": "hd", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "tbr": 800}]}
    assert qualities(info) == [Quality(720, "720p", "hd", 800 * 1000 // 8 * 100)]


def test_original_language_audio_beats_dubs_and_drc():
    info = {
        "formats": [
            video("137", 1080),
            audio("140-0", abr=160, language_preference=-1),
            audio("140-drc", abr=160, language_preference=10),
            audio("140-1", abr=128, language_preference=10),
        ],
    }
    assert qualities(info)[0].format_spec == "137+140-1"


def test_combined_format_needs_no_audio_and_unknown_size_is_none():
    info = {"formats": [{"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a"}, audio("140")]}
    assert qualities(info) == [Quality(360, "360p", "18", None)]


def test_portrait_video_is_named_by_its_short_side_and_high_fps_is_shown():
    info = {"formats": [video("x", 1920, width=1080, fps=60)]}
    assert qualities(info)[0].label == "1080p60"


def test_pick_default_takes_best_at_or_below_preferred():
    options = [Quality(h, f"{h}p", "x", None) for h in (2160, 1440, 1080, 720)]
    no_1080 = options[:2] + options[3:]
    only_high = options[:2]
    assert options[pick_default(options, 1080)].height == 1080
    assert no_1080[pick_default(no_1080, 1080)].height == 720
    assert only_high[pick_default(only_high, 1080)].height == 1440  # nothing lower: smallest there is


def options_with_1440p(size_1440):
    return [
        Quality(2160, "2160p", "a", 900 * MB),
        Quality(1440, "1440p", "b", size_1440),
        Quality(1080, "1080p", "c", 120 * MB),
        Quality(720, "720p", "d", 60 * MB),
    ]


def test_small_1440p_is_preselected_over_the_1080p_preference():
    options = options_with_1440p(299 * MB)
    assert options[pick_default(options, 1080)].height == 1440
    assert options[pick_default(options, 720)].height == 1440


def test_1440p_is_not_preselected_when_300_mb_or_more_or_of_unknown_size():
    for size in (300 * MB, 800 * MB, None):
        options = options_with_1440p(size)
        assert options[pick_default(options, 1080)].height == 1080


def test_1440p_rule_can_be_switched_off_and_never_lowers_a_higher_preference():
    options = options_with_1440p(100 * MB)
    assert options[pick_default(options, 1080, upgrade_small=False)].height == 1080
    assert options[pick_default(options, 2160)].height == 2160
    assert options[pick_default(options, 1440)].height == 1440


def test_human_readable_helpers():
    assert human_size(None) == "size unknown"
    assert human_size(419 * MB) == "419 MB"
    assert human_size(4.2 * 1024 * MB) == "4.20 GB"
    assert human_time(4182) == "1:09:42"
    assert human_time(65) == "1:05"
    assert human_eta(30) == "less than a minute"
    assert human_eta(7 * 60) == "about 7 min"
    assert human_eta(3900) == "about 1 h 05 min"
