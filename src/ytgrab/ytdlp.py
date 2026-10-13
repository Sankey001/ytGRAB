"""Build the yt-dlp commands the app runs, name the output files, and read the progress output."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ytgrab import tools

# One machine-readable line per progress tick instead of yt-dlp's human text.
PROGRESS_TAG = "YTGRAB"
PROGRESS_TEMPLATE = (
    f"download:{PROGRESS_TAG}|%(progress.downloaded_bytes)s|%(progress.total_bytes)s"
    "|%(progress.total_bytes_estimate)s|%(progress.speed)s"
)

# YouTube limits the speed of each connection, so a video's speed grows with the
# number of fragments fetched in parallel, until the line itself is full. Measured
# on one lecture: 8 fragments gave 2.5 MiB/s, 16 gave 4.9 and 32 gave 6.0, the
# line's limit. The budget below is shared out between the videos running at once.
CONNECTION_BUDGET = 40
MAX_FRAGMENTS = 32
MIN_FRAGMENTS = 6

# Parts of a lookup's answer that a download never reads; dropping them and the
# unused formats turns about 1 MB of JSON per video into a few kilobytes.
_UNNEEDED_INFO = (
    "automatic_captions",
    "subtitles",
    "thumbnails",
    "heatmap",
    "requested_formats",
    "requested_downloads",
    "requested_subtitles",
)

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def _base() -> list[str]:
    # --ignore-config: a yt-dlp config file on this machine must not change what the app does.
    args = [*tools.ytdlp_command(), "--ignore-config"]
    runtime = tools.js_runtime()
    if runtime:
        name, path = runtime
        args += ["--js-runtimes", f"{name}:{path}"]
    return args


def version_cmd() -> list[str]:
    return [*tools.ytdlp_command(), "--version"]


def list_cmd(url: str) -> list[str]:
    """Fast listing: playlist entries without their formats (or a full video, if it is one)."""
    return [*_base(), "--dump-single-json", "--flat-playlist", url]


def info_cmd(url: str) -> list[str]:
    """Full details of one video, including every available format."""
    return [*_base(), "--dump-single-json", "--no-playlist", url]


def fragments_for(videos_at_once: int) -> int:
    """How many fragments one video may fetch in parallel when this many videos share the line."""
    return max(MIN_FRAGMENTS, min(MAX_FRAGMENTS, CONNECTION_BUDGET // max(1, videos_at_once)))


def slim_info(info: dict, format_specs: list[str]) -> dict:
    """A lookup's answer cut down to what downloading any of `format_specs` needs.

    Saved and handed back to yt-dlp with --load-info-json, it lets the download
    start without looking the video up a second time.
    """
    wanted = {part for spec in format_specs for part in spec.split("+")}
    slim = {key: value for key, value in info.items() if key not in _UNNEEDED_INFO}
    slim["formats"] = [fmt for fmt in info.get("formats") or [] if str(fmt.get("format_id")) in wanted]
    return slim


def download_cmd(
    url: str, format_spec: str, output_template: str, fragments: int = 8, info_file: str | None = None
) -> list[str]:
    """The download command. With `info_file` (see `slim_info`), yt-dlp reads that instead of asking the site again."""
    ffmpeg = tools.ffmpeg_path()
    return [
        *_base(),
        *(["--ffmpeg-location", ffmpeg] if ffmpeg else []),
        "--format", format_spec,
        "--concurrent-fragments", str(fragments),
        "--merge-output-format", "mp4",
        "--windows-filenames",  # names that are valid on every filesystem, NTFS and exFAT included
        "--no-playlist",
        "--retries", "20",
        "--fragment-retries", "20",
        "--newline",
        "--progress-template", PROGRESS_TEMPLATE,
        "--output", output_template,
        *(["--load-info-json", info_file] if info_file else [url]),
    ]  # fmt: skip


def safe_name(name: str) -> str:
    """A folder name that is valid on Windows, macOS and Linux alike."""
    cleaned = _UNSAFE.sub("_", name).strip(" .")
    if _WINDOWS_RESERVED.match(cleaned):
        cleaned = "_" + cleaned
    return cleaned or "Playlist"


def number_prefix(index: int, count: int | None = None) -> str:
    """'03 - ' style prefix, zero-padded to the playlist's size so names sort in playlist order."""
    width = max(2, len(str(max(index, count or 0))))
    return f"{index:0{width}d} - "


def output_template(
    folder: str, label: str, playlist: str | None = None, index: int | None = None, count: int | None = None
) -> str:
    """Where a video lands: playlists get their own subfolder with numbered files."""

    def literal(text: str) -> str:
        return text.replace("%", "%%")  # % starts a yt-dlp field

    directory = str(folder)
    prefix = ""
    if playlist:
        directory = os.path.join(directory, safe_name(playlist))
        if index is not None:
            prefix = number_prefix(index, count)
    return os.path.join(literal(directory), f"{prefix}%(title)s ({literal(label)}).%(ext)s")


@dataclass(frozen=True)
class Progress:
    downloaded: int
    total: int | None
    speed: float | None


def _number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:  # yt-dlp prints "NA" for unknown fields
        return None


def parse_progress(line: str) -> Progress | None:
    """Read one line of our progress template; None for any other line."""
    if not line.startswith(PROGRESS_TAG + "|"):
        return None
    fields = line.strip().split("|")
    if len(fields) != 5:
        return None
    downloaded = _number(fields[1])
    if downloaded is None:
        return None
    total = _number(fields[2]) or _number(fields[3])
    return Progress(int(downloaded), int(total) if total else None, _number(fields[4]))
