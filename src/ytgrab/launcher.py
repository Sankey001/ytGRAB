"""Put ytgrab where each system keeps its apps.

Linux gets a .desktop entry, Windows a Start menu shortcut, macOS an .app in
~/Applications.  Each one simply starts the already-installed ytgrab, so
installing again after moving or reinstalling ytgrab repairs it.
"""

from __future__ import annotations

import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sysconfig
from pathlib import Path

from ytgrab import __version__, tools

ASSETS = Path(__file__).parent / "assets"
COMMENT = "Download videos and playlists with yt-dlp"


def menu_name() -> str:
    """What this system calls the place the launcher goes."""
    if tools.WINDOWS:
        return "Start menu"
    return "Applications folder" if tools.MACOS else "applications menu"


def start_command() -> list[str]:
    """How to start the app from outside a terminal: the installed `ytgrab` script, else `python -m ytgrab`."""
    script = Path(sysconfig.get_path("scripts")) / ("ytgrab.exe" if tools.WINDOWS else "ytgrab")
    if script.exists():
        return [str(script)]
    return [tools.gui_python(), "-m", "ytgrab"]


def install() -> Path:
    """Create or refresh the launcher; returns what was written."""
    if tools.WINDOWS:
        return _install_windows()
    if tools.MACOS:
        return _install_macos()
    return _install_linux()


# ------------------------------------------------------------------- Linux


def _desktop_quote(argument: str) -> str:
    """Quote one argument for the Exec line of a .desktop file."""
    argument = argument.replace("%", "%%")  # % starts a field code there
    if re.fullmatch(r"[A-Za-z0-9_./:=@+-]+", argument):
        return argument
    return '"' + re.sub(r'(["`$\\])', r"\\\1", argument) + '"'


def _install_linux() -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    icon = data / "icons" / "hicolor" / "256x256" / "apps" / "ytgrab.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / "icon.png", icon)

    entry = data / "applications" / "ytgrab.desktop"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ytgrab\n"
        "GenericName=Video Downloader\n"
        f"Comment={COMMENT}\n"
        f"Exec={' '.join(_desktop_quote(part) for part in start_command())}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Network;\n"
        "Keywords=video;playlist;download;yt-dlp;\n"
        "StartupNotify=true\n"
        "StartupWMClass=ytgrab\n",
        encoding="utf-8",
    )
    return entry


# ----------------------------------------------------------------- Windows

# The shortcut is made by the Windows Script Host through PowerShell, which every
# supported Windows has. Values travel as environment variables, so no quoting is needed.
_SHORTCUT_SCRIPT = (
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:YTGRAB_LNK); "
    "$s.TargetPath = $env:YTGRAB_TARGET; "
    "$s.Arguments = $env:YTGRAB_ARGS; "
    "$s.IconLocation = $env:YTGRAB_ICON; "
    "$s.Description = $env:YTGRAB_COMMENT; "
    "$s.Save()"
)


def _install_windows() -> Path:
    programs = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    programs.mkdir(parents=True, exist_ok=True)
    shortcut = programs / "ytgrab.lnk"
    command = start_command()
    values = {
        "YTGRAB_LNK": str(shortcut),
        "YTGRAB_TARGET": command[0],
        "YTGRAB_ARGS": subprocess.list2cmdline(command[1:]),
        "YTGRAB_ICON": str(ASSETS / "icon.ico"),
        "YTGRAB_COMMENT": COMMENT,
    }
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SHORTCUT_SCRIPT],
        env={**os.environ, **values},
        check=True,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return shortcut


# ------------------------------------------------------------------- macOS


def _install_macos() -> Path:
    app = Path.home() / "Applications" / "ytgrab.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(exist_ok=True)
    shutil.copyfile(ASSETS / "icon.icns", contents / "Resources" / "ytgrab.icns")

    runner = contents / "MacOS" / "ytgrab"
    runner.write_text(f'#!/bin/sh\nexec {shlex.join(start_command())} "$@"\n', encoding="utf-8")
    runner.chmod(0o755)

    with open(contents / "Info.plist", "wb") as plist:
        plistlib.dump(
            {
                "CFBundleName": "ytgrab",
                "CFBundleDisplayName": "ytgrab",
                "CFBundleIdentifier": "org.ytgrab.app",
                "CFBundleExecutable": "ytgrab",
                "CFBundleIconFile": "ytgrab",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": __version__,
                "CFBundleVersion": __version__,
                "NSHighResolutionCapable": True,
            },
            plist,
        )
    return app
