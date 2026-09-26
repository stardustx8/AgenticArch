from __future__ import annotations

import heapq

from .errors import DuplicateJob, QueueEmpty
from .job import Job


class JobQueue:
    """Priority queue of jobs; lower priority numbers are served first."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, Job]] = []
        self._pending: set[str] = set()

    def submit(self, job: Job) -> None:
        """Queue *job*. Raises DuplicateJob if a job with the same id is pending."""
        if job.id in self._pending:
            raise DuplicateJob(job.id)
        heapq.heappush(self._heap, (job.priority, job))
        self._pending.add(job.id)

    def pop(self) -> Job:
        """Remove and return the next job to run."""
        if not self._heap:
            raise QueueEmpty("no pending jobs")
        _, job = heapq.heappop(self._heap)
        self._pending.discard(job.id)
        return job

    def peek(self) -> Job:
        """Return the next job to run without removing it."""
        if not self._heap:
            raise QueueEmpty("no pending jobs")
        return self._heap[0][1]

    def pending_ids(self) -> list[str]:
        """Ids of pending jobs, in the order they would be popped."""
        return [job.id for _, job in sorted(self._heap)]

    def __len__(self) -> int:
        return len(self._heap)

    def __contains__(self, job_id: object) -> bool:
        return job_id in self._pending
