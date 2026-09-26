"""A small least-recently-used cache with optional per-entry expiry."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Hashable, Iterator, NamedTuple

from .clock import Clock, monotonic
from .stats import CacheStats


class _Entry(NamedTuple):
    value: Any
    expires_at: float | None

    def expired(self, now: float) -> bool:
        return self.expires_at is not None and now >= self.expires_at


class LRUCache:
    """Fixed-capacity mapping that evicts the least recently used key.

    ``clock`` is a zero-argument callable returning seconds; it timestamps
    accesses in :attr:`stats` and decides when entries expire. An entry set
    with a ``ttl`` (or under ``default_ttl``) disappears once the clock
    reaches its set time plus the ttl.
    """

    def __init__(
        self,
        capacity: int,
        clock: Clock = monotonic,
        default_ttl: float | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        _check_ttl(default_ttl)
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.stats = CacheStats()
        self._clock = clock
        self._data: OrderedDict[Hashable, _Entry] = OrderedDict()

    def get(self, key: Hashable, default: Any = None) -> Any:
        now = self._clock()
        entry = self._live_entry(key, now)
        if entry is None:
            self.stats.record_miss(now)
            return default
        self._data.move_to_end(key)
        self.stats.record_hit(now)
        return entry.value

    def set(self, key: Hashable, value: Any, ttl: float | None = None) -> None:
        if ttl is None:
            ttl = self.default_ttl
        _check_ttl(ttl)
        now = self._clock()
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self.capacity:
            self._purge_expired(now)
            if len(self._data) >= self.capacity:
                self._evict()
        expires_at = None if ttl is None else now + ttl
        self._data[key] = _Entry(value, expires_at)

    def delete(self, key: Hashable) -> bool:
        """Remove ``key`` and report whether a live entry was present."""
        entry = self._data.pop(key, None)
        return entry is not None and not entry.expired(self._clock())

    def clear(self) -> None:
        self._data.clear()

    def keys(self) -> list[Hashable]:
        """Return live keys ordered from least to most recently used."""
        self._purge_expired(self._clock())
        return list(self._data)

    def __contains__(self, key: object) -> bool:
        return self._live_entry(key, self._clock()) is not None

    def __len__(self) -> int:
        self._purge_expired(self._clock())
        return len(self._data)

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self.keys())

    def __repr__(self) -> str:
        return f"{type(self).__name__}(capacity={self.capacity}, size={len(self)})"

    def _live_entry(self, key: Hashable, now: float) -> _Entry | None:
        entry = self._data.get(key)
        if entry is not None and entry.expired(now):
            del self._data[key]
            return None
        return entry

    def _purge_expired(self, now: float) -> None:
        for key in [k for k, entry in self._data.items() if entry.expired(now)]:
            del self._data[key]

    def _evict(self) -> None:
        self._data.popitem(last=False)
        self.stats.record_eviction()


def _check_ttl(ttl: float | None) -> None:
    if ttl is not None and ttl <= 0:
        raise ValueError(f"ttl must be positive, got {ttl!r}")
