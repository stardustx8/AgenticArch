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
            self.snapshots.save(Snapshot(event.account_id, state.version, state))

    def load(self, account_id):
        snap = self.snapshots.latest(account_id)
        if snap is None:
            return project(account_id, self.store.events_for(account_id))
        events = self.store.events_for(account_id, after_seq=snap.version)
        return project(account_id, events, initial=snap.state)
