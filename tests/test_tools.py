"""The helper programs must be found and must actually run on whichever system the tests run on."""

import os
import sysconfig
from pathlib import Path

import pytest

from ytgrab import tools


@pytest.fixture(autouse=True)
def fresh_ffmpeg_lookup():
    """ffmpeg_path() remembers its answer; forget it around each test."""
    tools.ffmpeg_path.cache_clear()
    yield
    tools.ffmpeg_path.cache_clear()


def test_the_console_python_exists():
    assert Path(tools.python_executable()).exists()
    assert Path(tools.gui_python()).exists()


def test_ytdlp_runs_as_a_module_of_this_python(monkeypatch):
    monkeypatch.delenv("YTGRAB_YTDLP", raising=False)
    assert tools.ytdlp_command() == [tools.python_executable(), "-m", "yt_dlp"]


def test_ytdlp_can_be_pointed_elsewhere(monkeypatch):
    monkeypatch.setenv("YTGRAB_YTDLP", "my-yt-dlp")
    assert tools.ytdlp_command() == ["my-yt-dlp"]


def test_search_path_puts_this_environment_first_and_keeps_the_rest():
    parts = tools.search_path().split(os.pathsep)
    assert parts[0] == sysconfig.get_path("scripts")
    assert os.environ["PATH"].split(os.pathsep)[0] in parts


def test_bundled_ffmpeg_is_used_when_the_system_has_none(monkeypatch):
    monkeypatch.delenv("YTGRAB_FFMPEG", raising=False)
    monkeypatch.setattr(tools, "find_tool", lambda _name: None)
    bundled = tools.ffmpeg_path()
    assert bundled and Path(bundled).exists()
    assert "imageio_ffmpeg" in bundled


def test_ffmpeg_can_be_pointed_elsewhere(monkeypatch):
    monkeypatch.setenv("YTGRAB_FFMPEG", "my-ffmpeg")
    assert tools.ffmpeg_path() == "my-ffmpeg"


def test_a_javascript_runtime_is_found():
    name, path = tools.js_runtime()
    assert name in tools.JS_RUNTIMES
    assert Path(path).exists()


def test_children_get_our_path_and_utf8_output():
    env = tools.child_environment()
    assert env["PATH"] == tools.search_path()
    assert env["PYTHONUTF8"] == "1"


def test_display_command_quotes_for_this_systems_shell():
    shown = tools.display_command(["prog", "two words", "plain"])
    assert shown.startswith("prog ") and shown.endswith(" plain")
    assert "two words" in shown and shown != "prog two words plain"


def test_every_helper_actually_runs():
    """The real thing: start yt-dlp, ffmpeg and the JavaScript runtime once each."""
    rows = tools.check()
    assert [name for name, _works, _detail in rows] == ["yt-dlp", "ffmpeg", "JavaScript runtime"]
    assert all(works for _name, works, _detail in rows), rows


def test_the_bundled_ffmpeg_actually_runs(monkeypatch):
    monkeypatch.delenv("YTGRAB_FFMPEG", raising=False)
    monkeypatch.setattr(tools, "find_tool", lambda name: None if name == "ffmpeg" else tools.shutil.which(name, path=tools.search_path()))
    rows = dict((name, (works, detail)) for name, works, detail in tools.check())
    works, detail = rows["ffmpeg"]
    assert works and "imageio_ffmpeg" in detail, detail
