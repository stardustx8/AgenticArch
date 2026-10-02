"""Token bucket rate limiting."""
from __future__ import annotations

import time
from typing import Callable

Clock = Callable[[], float]


class TokenBucket:
    """Classic token bucket.

    The bucket holds at most ``capacity`` tokens and gains ``refill_rate``
    tokens per second, continuously. It starts full.
    """

    def __init__(self, capacity: int, refill_rate: float, clock: Clock = time.monotonic) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed <= 0:
            return
        self._tokens = min(float(self.capacity), self._tokens + elapsed * self.refill_rate)
        self._last = now

    def available(self) -> float:
        """Return the number of tokens currently in the bucket (may be fractional)."""
        self._refill()
        return self._tokens

    def try_acquire(self, n: int = 1) -> bool:
        """Take ``n`` tokens if they are available; return whether it succeeded."""
        if n <= 0 or n > self.capacity:
            raise ValueError(f"n must be between 1 and {self.capacity}, got {n}")
        self._refill()
        if n > self._tokens:
            return False
        self._tokens -= n
        return True

    def time_until(self, n: int = 1) -> float:
        """Seconds until ``n`` tokens would be available (0.0 if they already are)."""
        self._refill()
        missing = n - self._tokens
        if missing <= 0:
            return 0.0
        return missing / self.refill_rate

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(capacity={self.capacity}, "
            f"refill_rate={self.refill_rate}, tokens={self._tokens})"
        )
