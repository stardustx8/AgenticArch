"""Fixed-window request rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

Clock = Callable[[], float]


class RateLimiter:
    """Allow at most ``limit`` requests per ``window`` seconds for each key."""

    def __init__(self, limit: int, window: float, clock: Clock = time.monotonic) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window <= 0:
            raise ValueError("window must be positive")
        self.limit = limit
        self.window = window
        self._clock = clock
        self._counts: Dict[Tuple[str, int], int] = defaultdict(int)

    def _slot(self, key: str, now: float) -> Tuple[str, int]:
        return key, int(now // self.window)

    def allow(self, key: str) -> bool:
        """Record a request for ``key`` and return whether it is permitted."""
        slot = self._slot(key, self._clock())
        if self._counts[slot] >= self.limit:
            return False
        self._counts[slot] += 1
        self._prune(slot[1])
        return True

    def remaining(self, key: str) -> int:
        """How many more requests ``key`` may make right now."""
        slot = self._slot(key, self._clock())
        return max(0, self.limit - self._counts.get(slot, 0))

    def reset(self, key: str) -> None:
        for slot in [s for s in self._counts if s[0] == key]:
            del self._counts[slot]

    def _prune(self, current: int) -> None:
        for slot in [s for s in self._counts if s[1] < current]:
            del self._counts[slot]
