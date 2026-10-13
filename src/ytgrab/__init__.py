"""ytgrab: a small desktop app on top of yt-dlp for downloading videos and playlists."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ytgrab")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
