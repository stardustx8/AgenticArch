"""Sliding-window request rate limiting."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Iterable, List, Optional

Clock = Callable[[], float]


@dataclass(frozen=True)
class Rule:
    """At most ``limit`` requests in any ``window``-second span."""

    limit: int
    window: float

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.window <= 0:
            raise ValueError("window must be positive")


class RateLimiter:
    """Sliding-window limiter enforcing one or more rules per key.

    A request made at time ``t`` counts against a rule until ``t + window``.
    Only allowed requests are recorded.
    """

    def __init__(
        self,
        limit: Optional[int] = None,
        window: Optional[float] = None,
        clock: Clock = time.monotonic,
        *,
        rules: Optional[Iterable[Rule]] = None,
    ) -> None:
        if rules is None:
            if limit is None or window is None:
                raise ValueError("pass either limit and window, or rules")
            rules = [Rule(limit, window)]
        elif limit is not None or window is not None:
            raise ValueError("pass either limit and window, or rules, not both")
        self.rules: List[Rule] = list(rules)
        if not self.rules:
            raise ValueError("at least one rule is required")
        self._clock = clock
        self._horizon = max(rule.window for rule in self.rules)
        self._hits: Dict[str, Deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Record a request for ``key`` and return whether it is permitted."""
        now = self._clock()
        if self._wait(key, now) > 0:
            return False
        self._hits.setdefault(key, deque()).append(now)
        return True

    def retry_after(self, key: str) -> float:
        """Seconds until ``key`` may make another request (0.0 if it may now)."""
        return self._wait(key, self._clock())

    def remaining(self, key: str) -> int:
        """How many more requests ``key`` may make right now."""
        now = self._clock()
        self._prune(key, now)
        return min(
            max(0, rule.limit - len(self._in_window(key, rule, now))) for rule in self.rules
        )

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def _wait(self, key: str, now: float) -> float:
        self._prune(key, now)
        wait = 0.0
        for rule in self.rules:
            recent = self._in_window(key, rule, now)
            if len(recent) >= rule.limit:
                wait = max(wait, recent[-rule.limit] + rule.window - now)
        return wait

    def _in_window(self, key: str, rule: Rule, now: float) -> List[float]:
        return [t for t in self._hits.get(key, ()) if t + rule.window > now]

    def _prune(self, key: str, now: float) -> None:
        hits = self._hits.get(key)
        if hits is None:
            return
        while hits and hits[0] + self._horizon <= now:
            hits.popleft()
        if not hits:
            del self._hits[key]
