"""A small least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Hashable, Iterator

from .clock import Clock, monotonic
from .stats import CacheStats

_MISSING = object()


class LRUCache:
    """Fixed-capacity mapping that evicts the least recently used key.

    ``clock`` is a zero-argument callable returning seconds; it is used to
    timestamp accesses in :attr:`stats`.
    """

    def __init__(self, capacity: int, clock: Clock = monotonic) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.stats = CacheStats()
        self._clock = clock
        self._data: OrderedDict[Hashable, Any] = OrderedDict()

    def get(self, key: Hashable, default: Any = None) -> Any:
        now = self._clock()
        value = self._data.get(key, _MISSING)
        if value is _MISSING:
            self.stats.record_miss(now)
            return default
        self._data.move_to_end(key)
        self.stats.record_hit(now)
        return value

    def set(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self.capacity:
            self._evict()
        self._data[key] = value

    def delete(self, key: Hashable) -> bool:
        """Remove ``key`` and report whether it was present."""
        return self._data.pop(key, _MISSING) is not _MISSING

    def clear(self) -> None:
        self._data.clear()

    def keys(self) -> list[Hashable]:
        """Return keys ordered from least to most recently used."""
        return list(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self.keys())

    def __repr__(self) -> str:
        return f"{type(self).__name__}(capacity={self.capacity}, size={len(self)})"

    def _evict(self) -> None:
        self._data.popitem(last=False)
        self.stats.record_eviction()
