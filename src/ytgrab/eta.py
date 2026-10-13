"""Download speed and time-left estimate."""

from __future__ import annotations

from collections import deque


class SpeedMeter:
    """Sliding-window average over the last `window` seconds of (time, bytes) samples."""

    def __init__(self, window: float = 15.0) -> None:
        self.window = window
        self._samples: deque[tuple[float, int]] = deque()

    def add(self, now: float, total_bytes: int) -> None:
        self._samples.append((now, total_bytes))
        while len(self._samples) > 2 and now - self._samples[0][0] > self.window:
            self._samples.popleft()

    def speed(self) -> float | None:
        """Bytes per second, or None until there is enough data."""
        if len(self._samples) < 2:
            return None
        (t0, b0), (t1, b1) = self._samples[0], self._samples[-1]
        if t1 <= t0 or b1 <= b0:
            return None
        return (b1 - b0) / (t1 - t0)

    def eta(self, remaining_bytes: float) -> float | None:
        speed = self.speed()
        if not speed:
            return None
        return max(remaining_bytes, 0) / speed
