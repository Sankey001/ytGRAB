"""Work out what kind of link the user dropped in, without touching the network."""

from __future__ import annotations

import re
from enum import Enum
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}
SHORT_HOSTS = {"youtu.be"}
VIDEO_PATHS = ("/shorts/", "/live/", "/embed/", "/v/")
CHANNEL_PATHS = ("/@", "/channel/", "/c/", "/user/")

_BARE_DOMAIN = re.compile(r"^[\w-]+(\.[\w-]+)+(/|$)")


class UrlKind(Enum):
    VIDEO = "Video"
    PLAYLIST = "Playlist"
    OTHER = "Link"  # not YouTube; yt-dlp decides what it is when we fetch
    INVALID = "Not a link"
    EMPTY = ""


def normalize(text: str) -> str:
    """Trim the text and add https:// to links pasted without a scheme."""
    text = text.strip()
    if text and "://" not in text and _BARE_DOMAIN.match(text):
        text = "https://" + text
    return text


def classify(text: str) -> UrlKind:
    url = normalize(text)
    if not url:
        return UrlKind.EMPTY

    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or "." not in parts.netloc:
        return UrlKind.INVALID

    host = parts.netloc.lower().split(":")[0].removeprefix("www.")
    path = parts.path
    query = parse_qs(parts.query)

    if host in SHORT_HOSTS:
        return UrlKind.VIDEO if path.strip("/") else UrlKind.INVALID

    if host in YOUTUBE_HOSTS:
        # A video opened from inside a playlist carries both v= and list=.
        # The share button means "this video", so the video wins.
        if path == "/watch" and query.get("v"):
            return UrlKind.VIDEO
        if path.startswith(VIDEO_PATHS):
            return UrlKind.VIDEO
        if query.get("list") or path.startswith(CHANNEL_PATHS):
            return UrlKind.PLAYLIST
        return UrlKind.INVALID

    return UrlKind.OTHER


def split_links(text: str) -> list[str]:
    """Split pasted or dropped text into separate links."""
    return [normalize(token) for token in text.split() if classify(token) not in (UrlKind.EMPTY, UrlKind.INVALID)]
