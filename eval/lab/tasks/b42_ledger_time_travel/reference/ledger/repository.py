from dataclasses import replace

from .errors import AccountNotFound
from .projection import project
from .snapshots import Snapshot


class AccountRepository:
    """Records events and rebuilds account state, snapshotting every N events."""

    def __init__(self, store, snapshots, snapshot_every=5):
        if snapshot_every < 1:
            raise ValueError('snapshot_every must be >= 1')
        self.store = store
        self.snapshots = snapshots
        self.snapshot_every = snapshot_every

    def record(self, event):
        self.store.append(event)
        if event.seq % self.snapshot_every == 0:
            state = self.load(event.account_id)
            # Store a private copy so nobody holding ``state`` can alter the snapshot.
            self.snapshots.save(Snapshot(event.account_id, state.version, replace(state)))

    def load(self, account_id, as_of=None):
        """Rebuild an account at its latest version, or as it was right after ``as_of``."""
        current = self.store.last_seq(account_id)
        if current == 0:
            raise AccountNotFound(account_id)
        if as_of is None:
            as_of = current
        elif not 1 <= as_of <= current:
            raise ValueError(f'{account_id}: as_of must be between 1 and {current}, got {as_of}')
        snap = self.snapshots.latest_at_or_before(account_id, as_of)
        if snap is None:
            initial, after_seq = None, 0
        else:
            # Replay onto a copy: stored snapshots must never change.
            initial, after_seq = replace(snap.state), snap.version
        events = [
            e for e in self.store.events_for(account_id, after_seq=after_seq) if e.seq <= as_of
        ]
        return project(account_id, events, initial=initial)
