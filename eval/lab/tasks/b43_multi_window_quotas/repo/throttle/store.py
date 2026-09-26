"""In-memory home for sliding logs."""

from .window import SlidingLog


class LogStore:
    """Keeps one :class:`SlidingLog` per (user, window name)."""

    def __init__(self) -> None:
        self._logs: dict[tuple[str, str], SlidingLog] = {}

    def log(self, user: str, window_name: str) -> SlidingLog:
        key = (user, window_name)
        log = self._logs.get(key)
        if log is None:
            log = self._logs[key] = SlidingLog()
        return log

    def forget(self, user: str) -> None:
        for key in [key for key in self._logs if key[0] == user]:
            del self._logs[key]

    def __len__(self) -> int:
        return len(self._logs)
