"""Shared test setup: Qt without a display, no animation, and settings kept away from the real ones."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # must be set before Qt is imported
os.environ.setdefault("YTGRAB_MOTION", "off")  # changes land at once, so nothing here depends on timing

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication a process may have."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Send the app's settings to a throwaway file, so tests never read or change a real ytgrab's.

    QSettings.setDefaultFormat() cannot do this: Qt ignores it for the
    QSettings(organisation, application) constructor. The app's own
    YTGRAB_SETTINGS override works on every system.
    """
    path = tmp_path / "settings.ini"
    monkeypatch.setenv("YTGRAB_SETTINGS", str(path))
    monkeypatch.delenv("YTGRAB_THEME", raising=False)  # a developer's own choice must not decide the tests
    return path
