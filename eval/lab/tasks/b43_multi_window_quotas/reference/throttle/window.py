"""Sliding log of timestamped, weighted events."""

from collections import deque


class SlidingLog:
    """Events kept in arrival order as ``(moment, cost)`` pairs."""

    def __init__(self) -> None:
        self._events: deque[tuple[float, int]] = deque()
        self._total = 0

    def record(self, moment: float, cost: int) -> None:
        if self._events and moment < self._events[-1][0]:
            raise ValueError('events must be recorded in time order')
        self._events.append((moment, cost))
        self._total += cost

    def prune(self, now: float, seconds: float) -> None:
        """Drop events that no longer fall inside the window of ``seconds`` ending at ``now``.

        An event at ``t`` counts while ``now - t < seconds``; it stops counting
        at exactly ``t + seconds``.
        """
        while self._events and now - self._events[0][0] >= seconds:
            _, cost = self._events.popleft()
            self._total -= cost

    def total(self) -> int:
        return self._total

    def oldest(self) -> float | None:
        return self._events[0][0] if self._events else None

    def entries(self) -> list[tuple[float, int]]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)
