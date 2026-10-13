"""Turn yt-dlp's video JSON into the short list of qualities shown in the table."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HEIGHT = 1080
STANDARD_HEIGHTS = (2160, 1440, 1080, 720, 480, 360, 240, 144)

# A 1440p version this small is preselected even when the preference is lower.
UPGRADE_HEIGHT = 1440
UPGRADE_MAX_BYTES = 300 * 1024 * 1024


@dataclass(frozen=True)
class Quality:
    height: int
    label: str  # "1080p", "1080p60"
    format_spec: str  # passed to yt-dlp -f, e.g. "270+234"
    size: int | None  # bytes, video plus audio; None when yt-dlp can't tell

    def describe(self) -> str:
        return f"{self.label}  ·  {human_size(self.size)}"


# yt-dlp writes the string "none" for "no such stream" and null for "unknown".
# YouTube's HLS audio tracks have an unknown codec, so only "none" means absent.


def _is_video(fmt: dict) -> bool:
    return fmt.get("vcodec") != "none" and bool(fmt.get("height"))


def _is_audio_only(fmt: dict) -> bool:
    return fmt.get("vcodec") == "none" and fmt.get("acodec") != "none"


def _is_hls(fmt: dict) -> bool:
    return str(fmt.get("protocol", "")).startswith("m3u8")


def _needs_account(fmt: dict) -> bool:
    return "premium" in str(fmt.get("format_note", "")).lower()


def _codec_family(fmt: dict, key: str) -> str:
    return str(fmt.get(key) or "")[:4]  # "avc1", "vp09", "mp4a"...


def _estimate(fmt: dict, duration: float | None) -> int | None:
    """Rough size from the bitrate. HLS bitrates are peaks, so this runs high."""
    if fmt.get("filesize_approx"):
        return int(fmt["filesize_approx"])
    bitrate = fmt.get("tbr") or (fmt.get("vbr") or 0) + (fmt.get("abr") or 0)
    if bitrate and duration:
        return int(bitrate * 1000 / 8 * duration)
    return None


def _video_size(video: dict, videos: list[dict], duration: float | None) -> int | None:
    """Exact size, else the size of the same resolution and codec offered over plain https."""
    if video.get("filesize"):
        return int(video["filesize"])
    twins = [
        other
        for other in videos
        if other.get("filesize") and _codec_family(other, "vcodec") == _codec_family(video, "vcodec")
    ]
    if twins:
        exact = [other for other in twins if other.get("vcodec") == video.get("vcodec")]
        return int((exact or twins)[0]["filesize"])
    return _estimate(video, duration)


def _audio_size(audio: dict, audios: list[dict], duration: float | None) -> int | None:
    """Exact size, else the size of the best AAC track in the same language."""
    if audio.get("filesize"):
        return int(audio["filesize"])
    twins = [
        other
        for other in audios
        if other.get("filesize")
        and other.get("language") == audio.get("language")
        and _codec_family(other, "acodec") == "mp4a"
    ]
    if twins:
        return int(max(twins, key=lambda other: other.get("abr") or 0)["filesize"])
    return _estimate(audio, duration)


def _height(fmt: dict) -> int | None:
    """The 'p' number. Portrait videos are named by their short side, as YouTube does."""
    height, width = fmt.get("height"), fmt.get("width")
    if not height:
        return None
    return min(height, width) if width else height


def _video_rank(fmt: dict) -> tuple:
    # HLS first: it downloads in parallel fragments, which dodges YouTube's
    # per-connection throttling. Then H.264, which plays everywhere in an mp4.
    return (_is_hls(fmt), str(fmt.get("vcodec", "")).startswith("avc1"), fmt.get("tbr") or 0)


def _audio_rank(fmt: dict, want_hls: bool, position: int) -> tuple:
    return (
        fmt.get("language_preference") or -1,  # original language over dubs
        "drc" not in str(fmt.get("format_id", "")),
        _is_hls(fmt) == want_hls,  # same transport as the video, so both download fast
        _codec_family(fmt, "acodec") in ("mp4a", ""),  # AAC (or unknown) fits an mp4
        fmt.get("abr") or fmt.get("tbr") or 0,
        position,  # yt-dlp lists formats worst to best
    )


def qualities(info: dict) -> list[Quality]:
    """One entry per available resolution, best first."""
    duration = info.get("duration")
    formats = [fmt for fmt in info.get("formats") or [] if not _needs_account(fmt)]

    audios = [fmt for fmt in formats if _is_audio_only(fmt)]
    by_height: dict[int, list[dict]] = {}
    for fmt in formats:
        if _is_video(fmt):
            by_height.setdefault(_height(fmt), []).append(fmt)

    result = []
    for height in sorted(by_height, reverse=True):
        video = max(by_height[height], key=_video_rank)
        spec = str(video["format_id"])
        size = _video_size(video, by_height[height], duration)

        if video.get("acodec") == "none" and audios:
            hls = _is_hls(video)
            audio = max(audios, key=lambda fmt: _audio_rank(fmt, hls, formats.index(fmt)))
            spec += f"+{audio['format_id']}"
            audio_size = _audio_size(audio, audios, duration)
            if size is not None and audio_size is not None:
                size += audio_size

        fps = video.get("fps") or 0
        label = f"{height}p{round(fps)}" if fps >= 50 else f"{height}p"
        result.append(Quality(height, label, spec, size))
    return result


def pick_default(options: list[Quality], preferred: int = DEFAULT_HEIGHT, upgrade_small: bool = True) -> int:
    """Index of the quality to preselect.

    Normally the best one at or below `preferred`, else the smallest available.
    With `upgrade_small`, a 1440p version under 300 MB wins over a lower
    preference: the sharper picture costs little extra space.
    """
    if upgrade_small and preferred < UPGRADE_HEIGHT:
        for index, option in enumerate(options):
            if option.height == UPGRADE_HEIGHT and option.size is not None and option.size < UPGRADE_MAX_BYTES:
                return index
    for index, option in enumerate(options):  # options are sorted best first
        if option.height <= preferred:
            return index
    return len(options) - 1


def human_size(size: float | None) -> str:
    if size is None:
        return "size unknown"
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            # one decimal for small MB values, so a speed reads "2.4 MB/s" rather than "2 MB/s"
            return f"{size:.1f} {unit}" if unit == "MB" and size < 10 else f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def human_time(seconds: float | None) -> str:
    """Clock style for video lengths: 1:09:42."""
    if seconds is None:
        return "–"
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def human_eta(seconds: float | None) -> str:
    """Rounded wording for time left: 'about 7 min'."""
    if seconds is None:
        return "working out the time left…"
    if seconds < 60:
        return "less than a minute"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"about {minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"about {hours} h {minutes:02d} min"
