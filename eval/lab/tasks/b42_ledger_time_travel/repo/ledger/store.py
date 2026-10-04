from .errors import SequenceError


class EventStore:
    """Append-only in-memory event store with one stream per account."""

    def __init__(self):
        self._streams = {}

    def append(self, event):
        stream = self._streams.get(event.account_id, [])
        expected = len(stream) + 1
        if event.seq != expected:
            raise SequenceError(
                f'{event.account_id}: expected seq {expected}, got {event.seq}'
            )
        self._streams.setdefault(event.account_id, stream).append(event)

    def events_for(self, account_id, after_seq=0):
        """Events of one account with seq > after_seq, oldest first."""
        return [e for e in self._streams.get(account_id, []) if e.seq > after_seq]

    def last_seq(self, account_id):
        return len(self._streams.get(account_id, []))
