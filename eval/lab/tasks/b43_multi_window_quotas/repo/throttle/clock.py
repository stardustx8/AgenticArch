"""Clocks for the limiter. Times are floats in seconds."""

import time


class MonotonicClock:
    def now(self) -> float:
        return time.monotonic()


class ManualClock:
    """A clock that only moves when told to; handy for tests and simulations."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError('a clock cannot move backwards')
        self._now += seconds

    def set(self, moment: float) -> None:
        if moment < self._now:
            raise ValueError('a clock cannot move backwards')
        self._now = float(moment)
