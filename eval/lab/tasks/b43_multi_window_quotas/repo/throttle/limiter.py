"""Sliding-window rate limiting on top of quota policies."""

from dataclasses import dataclass

from .clock import MonotonicClock
from .quotas import QuotaPolicy
from .store import LogStore


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
        """Spend ``cost`` units for ``user`` if the quota allows it."""
        _validate_cost(cost)
        now = self.clock.now()
        window = self.policy.windows_for(user)[0]
        log = self.store.log(user, window.name)
        log.prune(now, window.seconds)
        used = log.total()
        if used + cost > window.limit:
            oldest = log.oldest()
            retry = oldest + window.seconds - now if oldest is not None else None
            return Decision(False, max(0, window.limit - used), retry)
        log.record(now, cost)
        return Decision(True, window.limit - used - cost, 0.0)

    def peek(self, user: str, cost: int = 1) -> Decision:
        """Report what ``check(user, cost)`` would decide now, without spending anything."""
        _validate_cost(cost)
        now = self.clock.now()
        window = self.policy.windows_for(user)[0]
        live = [
            (moment, spent)
            for moment, spent in self.store.log(user, window.name).entries()
            if now - moment <= window.seconds
        ]
        used = sum(spent for _, spent in live)
        if used + cost > window.limit:
            retry = live[0][0] + window.seconds - now if live else None
            return Decision(False, max(0, window.limit - used), retry)
        return Decision(True, window.limit - used - cost, 0.0)

    def reset(self, user: str) -> None:
        """Forget everything recorded for ``user``."""
        self.store.forget(user)


def _validate_cost(cost: int) -> None:
    if not isinstance(cost, int) or cost < 1:
        raise ValueError(f'cost must be a positive integer, got {cost!r}')
