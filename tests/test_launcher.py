"""Each system's launcher is written into a throwaway folder and inspected. Only the matching test runs."""

import os
import plistlib
import sys
from pathlib import Path

import pytest

from ytgrab import launcher

LINUX = sys.platform.startswith("linux")
WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"


def test_start_command_points_at_something_that_exists():
    assert Path(launcher.start_command()[0]).exists()


def test_every_system_has_its_icon_file():
    for name in ("icon.png", "icon.ico", "icon.icns"):
        assert (launcher.ASSETS / name).stat().st_size > 1000


def test_desktop_exec_quoting():
    assert launcher._desktop_quote("/usr/bin/ytgrab") == "/usr/bin/ytgrab"
    assert launcher._desktop_quote("/my apps/ytgrab") == '"/my apps/ytgrab"'
    assert launcher._desktop_quote("/odd$name") == '"/odd\\$name"'
    assert launcher._desktop_quote("50%") == '"50%%"'


@pytest.mark.skipif(not LINUX, reason="Linux launcher")
def test_linux_desktop_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    entry = launcher.install()

    assert entry == tmp_path / "applications" / "ytgrab.desktop"
    lines = dict(line.split("=", 1) for line in entry.read_text(encoding="utf-8").splitlines() if "=" in line)
    assert lines["Type"] == "Application" and lines["Terminal"] == "false"
    assert launcher.start_command()[0] in lines["Exec"]
    assert Path(lines["Icon"]).is_file() and Path(lines["Icon"]).is_relative_to(tmp_path)
    assert launcher.install() == entry  # installing again just refreshes it


@pytest.mark.skipif(not WINDOWS, reason="Windows launcher")
def test_windows_start_menu_shortcut(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    shortcut = launcher.install()

    assert shortcut == tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "ytgrab.lnk"
    assert shortcut.stat().st_size > 0


@pytest.mark.skipif(not MACOS, reason="macOS launcher")
def test_macos_app_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    app = launcher.install()

    assert app == tmp_path / "Applications" / "ytgrab.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "ytgrab" and info["CFBundleIconFile"] == "ytgrab"
    assert os.access(app / "Contents" / "MacOS" / "ytgrab", os.X_OK)
    assert (app / "Contents" / "Resources" / "ytgrab.icns").is_file()
