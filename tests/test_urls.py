import pytest

from ytgrab.urls import UrlKind, classify, normalize, split_links


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("https://youtu.be/6YnLB0XbTnI?si=abc", UrlKind.VIDEO),
        ("https://www.youtube.com/watch?v=6YnLB0XbTnI", UrlKind.VIDEO),
        ("https://www.youtube.com/shorts/abc123", UrlKind.VIDEO),
        ("https://youtube.com/playlist?list=PLangBM27OtEA&si=W1PP", UrlKind.PLAYLIST),
        ("https://www.youtube.com/@StanfordOnline/videos", UrlKind.PLAYLIST),
        # the share link of a video opened inside a playlist means that one video
        ("https://www.youtube.com/watch?v=6YnLB0XbTnI&list=PLangBM27OtEA", UrlKind.VIDEO),
        ("youtube.com/playlist?list=PLangBM27OtEA", UrlKind.PLAYLIST),
        ("https://vimeo.com/123456", UrlKind.OTHER),
        ("https://www.youtube.com/", UrlKind.INVALID),
        ("https://youtu.be/", UrlKind.INVALID),
        ("hello there", UrlKind.INVALID),
        ("   ", UrlKind.EMPTY),
    ],
)
def test_classify(text, kind):
    assert classify(text) is kind


def test_normalize_adds_scheme_only_to_bare_domains():
    assert normalize(" youtu.be/abc ") == "https://youtu.be/abc"
    assert normalize("https://youtu.be/abc") == "https://youtu.be/abc"
    assert normalize("not a link") == "not a link"


def test_split_links_keeps_only_links():
    text = "https://youtu.be/aaa\nsome words https://youtube.com/playlist?list=PL1\n"
    assert split_links(text) == ["https://youtu.be/aaa", "https://youtube.com/playlist?list=PL1"]
