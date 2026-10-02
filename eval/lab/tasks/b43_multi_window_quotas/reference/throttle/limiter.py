"""Sliding-window rate limiting on top of quota policies."""

from dataclasses import dataclass

from .clock import MonotonicClock
from .quotas import QuotaPolicy, Window
from .store import LogStore
from .window import SlidingLog


@dataclass(frozen=True)
class Decision:
    allowed: bool
    # Units still available after this decision (nothing is spent on a denial).
    remaining: int
    # Seconds to wait before the same request can succeed: 0.0 when allowed,
    # None when it can never succeed.
    retry_after: float | None


class RateLimiter:
    def __init__(self, policy: QuotaPolicy, clock=None, store: LogStore | None = None) -> None:
        self.policy = policy
        self.clock = clock if clock is not None else MonotonicClock()
        self.store = store if store is not None else LogStore()

    def check(self, user: str, cost: int = 1) -> Decision:
        """Spend ``cost`` units for ``user`` if every window allows it."""
        now = self.clock.now()
        decision, usage = self._evaluate(user, cost, now)
        if decision.allowed:
            for _, log in usage:
                log.record(now, cost)
        return decision

    def peek(self, user: str, cost: int = 1) -> Decision:
        """Report what ``check(user, cost)`` would decide now, without spending anything."""
        return self._evaluate(user, cost, self.clock.now())[0]

    def reset(self, user: str) -> None:
        """Forget everything recorded for ``user``."""
        self.store.forget(user)

    def _evaluate(self, user: str, cost: int, now: float) -> tuple[Decision, list[tuple[Window, SlidingLog]]]:
        _validate_cost(cost)
        usage = []
        for window in self.policy.windows_for(user):
            log = self.store.log(user, window.name)
            log.prune(now, window.seconds)
            usage.append((window, log))
        if all(log.total() + cost <= window.limit for window, log in usage):
            remaining = min(window.limit - log.total() - cost for window, log in usage)
            return Decision(True, remaining, 0.0), usage
        remaining = min(max(0, window.limit - log.total()) for window, log in usage)
        retry_after = 0.0
        for window, log in usage:
            wait = _wait_for_room(window, log, cost, now)
            if wait is None:
                retry_after = None
                break
            retry_after = max(retry_after, wait)
        return Decision(False, remaining, retry_after), usage


def _wait_for_room(window: Window, log: SlidingLog, cost: int, now: float) -> float | None:
    """Seconds until ``cost`` more units fit in ``window``, or None if they never will."""
    if cost > window.limit:
        return None
    excess = log.total() + cost - window.limit
    if excess <= 0:
        return 0.0
    freed = 0
    for moment, spent in log.entries():
        freed += spent
        if freed >= excess:
            return moment + window.seconds - now
    return None


def _validate_cost(cost: int) -> None:
    if not isinstance(cost, int) or cost < 1:
        raise ValueError(f'cost must be a positive integer, got {cost!r}')
