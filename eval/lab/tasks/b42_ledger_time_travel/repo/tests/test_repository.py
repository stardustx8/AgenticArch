import unittest

from ledger.errors import SequenceError
from ledger.events import AccountClosed, AccountOpened, Deposited, Withdrawn
from ledger.repository import AccountRepository
from ledger.snapshots import SnapshotStore
from ledger.store import EventStore


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.store = EventStore()
        self.snapshots = SnapshotStore()
        self.repo = AccountRepository(self.store, self.snapshots, snapshot_every=5)

    def _history(self, deposits):
        self.repo.record(AccountOpened('acc', 1, owner='ann'))
        for seq in range(2, deposits + 2):
            self.repo.record(Deposited('acc', seq, amount_cents=100))

    def test_record_and_load(self):
        self._history(3)
        self.repo.record(Withdrawn('acc', 5, amount_cents=50))
        state = self.repo.load('acc')
        self.assertEqual(state.balance_cents, 250)
        self.assertEqual(state.version, 5)
        self.assertEqual(state.owner, 'ann')

    def test_sequence_gap_rejected(self):
        self.repo.record(AccountOpened('acc', 1, owner='ann'))
        with self.assertRaises(SequenceError):
            self.repo.record(Deposited('acc', 3, amount_cents=100))

    def test_snapshot_taken_every_n_events(self):
        self._history(11)
        versions = [s.version for s in self.snapshots.all_for('acc')]
        self.assertEqual(versions, [5, 10])

    def test_load_replays_tail_after_snapshot(self):
        self._history(11)
        state = self.repo.load('acc')
        self.assertEqual(state.balance_cents, 1100)
        self.assertEqual(state.version, 12)

    def test_closed_account(self):
        self._history(1)
        self.repo.record(AccountClosed('acc', 3, reason='customer request'))
        self.assertEqual(self.repo.load('acc').status, 'closed')

    def test_load_unknown_account_returns_blank_state(self):
        state = self.repo.load('nobody')
        self.assertEqual(state.status, 'missing')
        self.assertEqual(state.version, 0)
        self.assertEqual(state.balance_cents, 0)

    def test_snapshot_every_must_be_positive(self):
        with self.assertRaises(ValueError):
            AccountRepository(self.store, self.snapshots, snapshot_every=0)
