import unittest

from ledger.events import AccountClosed, AccountOpened, Deposited, Withdrawn
from ledger.projection import AccountState, apply, project


class ProjectionTest(unittest.TestCase):
    def test_open_deposit_withdraw(self):
        events = [
            AccountOpened('a', 1, owner='ann'),
            Deposited('a', 2, amount_cents=500),
            Withdrawn('a', 3, amount_cents=120),
        ]
        state = project('a', events)
        self.assertEqual(state.owner, 'ann')
        self.assertEqual(state.status, 'open')
        self.assertEqual(state.balance_cents, 380)
        self.assertEqual(state.version, 3)

    def test_close_sets_status(self):
        state = project('a', [AccountOpened('a', 1, owner='bo'), AccountClosed('a', 2)])
        self.assertEqual(state.status, 'closed')
        self.assertEqual(state.version, 2)

    def test_blank_state_defaults(self):
        state = AccountState('a')
        self.assertEqual((state.status, state.version, state.balance_cents), ('missing', 0, 0))

    def test_unknown_event_rejected(self):
        with self.assertRaises(TypeError):
            apply(AccountState('a'), object())
