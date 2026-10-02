"""Per-client bucket bookkeeping."""
from __future__ import annotations

import time
from typing import Dict, Iterator

from .bucket import Clock, TokenBucket


class BucketRegistry:
    """Lazily creates one TokenBucket per client, all sharing the same config."""

    def __init__(self, capacity: int, refill_rate: float, clock: Clock = time.monotonic) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock
        self._buckets: Dict[str, TokenBucket] = {}

    def get(self, client_id: str) -> TokenBucket:
        bucket = self._buckets.get(client_id)
        if bucket is None:
            bucket = TokenBucket(self.capacity, self.refill_rate, clock=self._clock)
            self._buckets[client_id] = bucket
        return bucket

    def try_acquire(self, client_id: str, n: int = 1) -> bool:
        return self.get(client_id).try_acquire(n)

    def forget(self, client_id: str) -> None:
        self._buckets.pop(client_id, None)

    def __contains__(self, client_id: object) -> bool:
        return client_id in self._buckets

    def __len__(self) -> int:
        return len(self._buckets)

    def __iter__(self) -> Iterator[str]:
        return iter(self._buckets)
