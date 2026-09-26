"""Clock helpers so throttling logic can be tested without sleeping."""
from __future__ import annotations


class FakeClock:
    """A manually advanced monotonic clock.

    Instances are callable, so they can be passed anywhere a
    ``time.monotonic``-style function is expected.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot move a monotonic clock backwards")
        self._now += seconds

    def __repr__(self) -> str:
        return f"FakeClock(now={self._now})"
