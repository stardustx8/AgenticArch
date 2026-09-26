from __future__ import annotations

from typing import Callable

from .job import Job
from .queue import JobQueue

Handler = Callable[[Job], object]


def drain(queue: JobQueue, handler: Handler, limit: int | None = None) -> list[str]:
    """Run pending jobs through *handler* in queue order.

    Stops when the queue is empty or *limit* jobs have been processed and
    returns the ids that were handled, in order. If the handler raises, the
    exception propagates and the failing job is not requeued.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    processed: list[str] = []
    while len(queue) and (limit is None or len(processed) < limit):
        job = queue.pop()
        handler(job)
        processed.append(job.id)
    return processed
