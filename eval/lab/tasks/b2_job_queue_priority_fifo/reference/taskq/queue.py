from __future__ import annotations

import heapq
import itertools

from .errors import DuplicateJob, QueueEmpty
from .job import Job


class JobQueue:
    """Priority queue of jobs; lower priority numbers are served first.

    Jobs with equal priority are served in submission order.
    """

    def __init__(self) -> None:
        # Entries are (priority, sequence, job). The sequence number breaks ties
        # in submission order and identifies the live entry for each pending id;
        # cancelled entries stay in the heap and are skipped lazily.
        self._heap: list[tuple[int, int, Job]] = []
        self._pending: dict[str, int] = {}
        self._counter = itertools.count()

    def submit(self, job: Job) -> None:
        """Queue *job*. Raises DuplicateJob if a job with the same id is pending."""
        if job.id in self._pending:
            raise DuplicateJob(job.id)
        seq = next(self._counter)
        heapq.heappush(self._heap, (job.priority, seq, job))
        self._pending[job.id] = seq

    def cancel(self, job_id: str) -> bool:
        """Cancel the pending job *job_id*. Returns False if no such job is pending."""
        return self._pending.pop(job_id, None) is not None

    def pop(self) -> Job:
        """Remove and return the next job to run."""
        self._drop_cancelled()
        if not self._heap:
            raise QueueEmpty("no pending jobs")
        _, _, job = heapq.heappop(self._heap)
        del self._pending[job.id]
        return job

    def peek(self) -> Job:
        """Return the next job to run without removing it."""
        self._drop_cancelled()
        if not self._heap:
            raise QueueEmpty("no pending jobs")
        return self._heap[0][2]

    def pending_ids(self) -> list[str]:
        """Ids of pending jobs, in the order they would be popped."""
        return [job.id for _, seq, job in sorted(self._heap) if self._is_live(job.id, seq)]

    def __len__(self) -> int:
        return len(self._pending)

    def __contains__(self, job_id: object) -> bool:
        return job_id in self._pending

    def _is_live(self, job_id: str, seq: int) -> bool:
        return self._pending.get(job_id) == seq

    def _drop_cancelled(self) -> None:
        """Discard cancelled entries sitting at the top of the heap."""
        while self._heap:
            _, seq, job = self._heap[0]
            if self._is_live(job.id, seq):
                return
            heapq.heappop(self._heap)
