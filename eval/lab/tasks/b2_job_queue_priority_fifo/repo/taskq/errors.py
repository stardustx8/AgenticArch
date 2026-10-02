class TaskQueueError(Exception):
    """Base class for queue errors."""


class DuplicateJob(TaskQueueError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"job {job_id!r} is already pending")
        self.job_id = job_id


class QueueEmpty(TaskQueueError):
    """Raised when popping or peeking an empty queue."""
