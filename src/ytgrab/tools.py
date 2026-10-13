"""Find the helper programs ytgrab drives, the same way on Windows, macOS and Linux.

Everything needed ships as a Python dependency: yt-dlp (run as a module), Deno
(the JavaScript runtime yt-dlp uses for YouTube) and an ffmpeg binary.  A copy
already installed on the system is used where that is the better choice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from functools import lru_cache
from pathlib import Path

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"

JS_RUNTIMES = ("deno", "node", "bun")  # yt-dlp's own order of preference


def extra_dirs() -> list[str]:
    """Folders helper programs live in that an app started from a menu may not have on its PATH."""
    home = Path.home()
    dirs = [
        Path(sysconfig.get_path("scripts")),  # this Python environment: where the bundled deno lands
        home / ".local" / "bin",
        home / ".deno" / "bin",
    ]
    if MACOS:  # apps started from Finder do not get the shell's PATH
        dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    if WINDOWS:
        if os.environ.get("LOCALAPPDATA"):
            dirs.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links")
        dirs.append(home / "scoop" / "shims")
    return [str(folder) for folder in dirs if folder.is_dir()]


def search_path() -> str:
    """PATH with the extra folders in front; also handed to the programs we start."""
    return os.pathsep.join([*extra_dirs(), os.environ.get("PATH", "")])


def find_tool(name: str) -> str | None:
    return shutil.which(name, path=search_path())


def python_executable() -> str:
    """The console Python, for children whose output we read.

    On Windows a windowed app runs under pythonw.exe, which has no console
    streams of its own; python.exe sits next to it and behaves like everywhere else.
    """
    exe = Path(sys.executable)
    if WINDOWS and exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def gui_python() -> str:
    """The Python to start the app itself with: no console window on Windows."""
    exe = Path(sys.executable)
    if WINDOWS and exe.name.lower() == "python.exe" and exe.with_name("pythonw.exe").exists():
        return str(exe.with_name("pythonw.exe"))
    return str(exe)


def ytdlp_command() -> list[str]:
    """yt-dlp as installed alongside ytgrab. YTGRAB_YTDLP points at another copy instead."""
    override = os.environ.get("YTGRAB_YTDLP")
    return [override] if override else [python_executable(), "-m", "yt_dlp"]


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    """YTGRAB_FFMPEG if set, else a system ffmpeg, else the copy shipped with imageio-ffmpeg."""
    override = os.environ.get("YTGRAB_FFMPEG")
    if override:
        return override
    found = find_tool("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # not installed, or it has no binary for this machine
        return None


def js_runtime() -> tuple[str, str] | None:
    """(name, path) of the first JavaScript runtime found, or None."""
    for name in JS_RUNTIMES:
        path = find_tool(name)
        if path:
            return name, path
    return None


def child_environment() -> dict[str, str]:
    """Environment for the programs we start: our PATH, and UTF-8 output on every system."""
    return {**os.environ, "PATH": search_path(), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def display_command(cmd: list[str]) -> str:
    """A command as you would type it into this system's own shell."""
    if WINDOWS:
        return subprocess.list2cmdline(cmd)
    import shlex

    return shlex.join(cmd)


def _first_line(cmd: list[str]) -> str | None:
    """First line a command prints, or None if it cannot be run."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console window flashing up
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=child_environment(), creationflags=flags
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stdout or done.stderr).strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def check() -> list[tuple[str, bool, str]]:
    """Run each helper once. Returns (name, works, detail) rows; used by `python -m ytgrab --check`."""
    rows = []

    version = _first_line([*ytdlp_command(), "--version"])
    rows.append(("yt-dlp", version is not None, version or "does not run"))

    ffmpeg = ffmpeg_path()
    banner = _first_line([ffmpeg, "-version"]) if ffmpeg else None
    rows.append(("ffmpeg", banner is not None, f"{banner}  ({ffmpeg})" if banner else "not found"))

    runtime = js_runtime()
    answer = _first_line([runtime[1], "--version"]) if runtime else None
    detail = f"{answer}  ({runtime[1]})" if answer else "none found: install Deno or Node.js"
    rows.append(("JavaScript runtime", answer is not None, detail))
    return rows
