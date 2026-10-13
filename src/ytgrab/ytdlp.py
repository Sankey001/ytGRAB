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

FRAGMENTS_IN_PARALLEL = "8"
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


def download_cmd(url: str, format_spec: str, output_template: str) -> list[str]:
    ffmpeg = tools.ffmpeg_path()
    return [
        *_base(),
        *(["--ffmpeg-location", ffmpeg] if ffmpeg else []),
        "--format", format_spec,
        "--concurrent-fragments", FRAGMENTS_IN_PARALLEL,
        "--merge-output-format", "mp4",
        "--windows-filenames",  # names that are valid on every filesystem, NTFS and exFAT included
        "--no-playlist",
        "--retries", "20",
        "--fragment-retries", "20",
        "--newline",
        "--progress-template", PROGRESS_TEMPLATE,
        "--output", output_template,
        url,
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
