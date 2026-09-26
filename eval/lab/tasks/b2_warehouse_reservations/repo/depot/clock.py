"""Clocks used by the depot. Times are plain floats (seconds)."""

from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class FakeClock:
    """Manually driven clock for tests and simulations."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("cannot move the clock backwards")
        self._now += seconds
        return self._now

    def set(self, when: float) -> None:
        if when < self._now:
            raise ValueError("cannot move the clock backwards")
        self._now = float(when)
