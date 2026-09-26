from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    last_access: float | None = None

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if not self.lookups:
            return 0.0
        return self.hits / self.lookups

    def record_hit(self, now: float) -> None:
        self.hits += 1
        self.last_access = now

    def record_miss(self, now: float) -> None:
        self.misses += 1
        self.last_access = now

    def record_eviction(self) -> None:
        self.evictions += 1

    def reset(self) -> None:
        self.hits = self.misses = self.evictions = 0
        self.last_access = None
