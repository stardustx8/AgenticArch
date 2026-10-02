import unittest

from ledger.errors import AccountNotFound
from ledger.events import AccountOpened, Deposited
from ledger.repository import AccountRepository
from ledger.snapshots import SnapshotStore
from ledger.store import EventStore


class RecordingStore(EventStore):
    def __init__(self):
        super().__init__()
        self.after_seqs = []

    def events_for(self, account_id, after_seq=0):
        self.after_seqs.append(after_seq)
        return super().events_for(account_id, after_seq)


class HiddenTimeTravelTest(unittest.TestCase):
    def setUp(self):
        self.store = RecordingStore()
        self.snapshots = SnapshotStore()
        self.repo = AccountRepository(self.store, self.snapshots, snapshot_every=5)
        self.repo.record(AccountOpened('acc', 1, owner='ann'))
        for seq in range(2, 13):
            self.repo.record(Deposited('acc', seq, amount_cents=100))
        self.store.after_seqs.clear()

    def test_as_of_between_snapshots_uses_older_snapshot(self):
        state = self.repo.load('acc', as_of=7)
        self.assertEqual((state.version, state.balance_cents, state.status), (7, 600, 'open'))
        self.assertIn(5, self.store.after_seqs)
        self.assertTrue(all(seq <= 7 for seq in self.store.after_seqs))

    def test_as_of_before_first_snapshot_replays_from_start(self):
        state = self.repo.load('acc', as_of=3)
        self.assertEqual((state.version, state.balance_cents, state.owner), (3, 200, 'ann'))

    def test_as_of_first_event(self):
        state = self.repo.load('acc', as_of=1)
        self.assertEqual((state.version, state.balance_cents, state.status), (1, 0, 'open'))

    def test_as_of_exactly_on_snapshot(self):
        state = self.repo.load('acc', as_of=10)
        self.assertEqual((state.version, state.balance_cents), (10, 900))

    def test_as_of_current_version_matches_plain_load(self):
        self.assertEqual(self.repo.load('acc', as_of=12), self.repo.load('acc'))

    def test_as_of_out_of_range(self):
        for bad in (0, -1, 13):
            with self.subTest(as_of=bad):
                with self.assertRaises(ValueError):
                    self.repo.load('acc', as_of=bad)

    def test_repeated_loads_are_stable(self):
        first = self.repo.load('acc')
        second = self.repo.load('acc')
        third = self.repo.load('acc', as_of=11)
        self.assertEqual((first.version, first.balance_cents), (12, 1100))
        self.assertEqual((second.version, second.balance_cents), (12, 1100))
        self.assertEqual((third.version, third.balance_cents), (11, 1000))

    def test_loading_does_not_modify_snapshots(self):
        self.repo.load('acc')
        self.repo.load('acc', as_of=7)
        self.repo.load('acc')
        got = [(s.version, s.state.version, s.state.balance_cents) for s in self.snapshots.all_for('acc')]
        self.assertEqual(got, [(5, 5, 400), (10, 10, 900)])

    def test_mutating_loaded_state_does_not_leak(self):
        state = self.repo.load('acc', as_of=10)
        state.balance_cents = 0
        state.status = 'closed'
        again = self.repo.load('acc', as_of=10)
        self.assertEqual((again.balance_cents, again.status), (900, 'open'))
        self.assertEqual(self.repo.load('acc').balance_cents, 1100)

    def test_recording_after_time_travel_keeps_snapshots_consistent(self):
        self.repo.load('acc', as_of=6)
        for seq in range(13, 16):
            self.repo.record(Deposited('acc', seq, amount_cents=100))
        got = [(s.version, s.state.balance_cents) for s in self.snapshots.all_for('acc')]
        self.assertEqual(got, [(5, 400), (10, 900), (15, 1400)])
        self.assertEqual(self.repo.load('acc', as_of=14).balance_cents, 1300)


class HiddenMissingAccountTest(unittest.TestCase):
    def setUp(self):
        self.repo = AccountRepository(EventStore(), SnapshotStore(), snapshot_every=3)

    def test_unknown_account_raises(self):
        with self.assertRaises(AccountNotFound):
            self.repo.load('ghost')

    def test_unknown_account_is_a_key_error(self):
        with self.assertRaises(KeyError):
            self.repo.load('ghost')

    def test_unknown_account_with_as_of_raises_not_found(self):
        with self.assertRaises(AccountNotFound):
            self.repo.load('ghost', as_of=1)
