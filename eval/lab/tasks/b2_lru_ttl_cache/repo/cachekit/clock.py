"""Clock helpers.

Caches take a zero-argument callable returning seconds as a float so that
tests (and simulations) can control time explicitly.
"""

from __future__ import annotations

import time
from typing import Callable

Clock = Callable[[], float]

monotonic: Clock = time.monotonic


class FakeClock:
    """A manually driven clock for tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot move a clock backwards")
        self._now += seconds

    def set(self, now: float) -> None:
        if now < self._now:
            raise ValueError("cannot move a clock backwards")
        self._now = float(now)
