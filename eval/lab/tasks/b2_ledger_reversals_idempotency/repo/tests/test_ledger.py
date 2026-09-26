import unittest

from ledger import InsufficientFunds, InvalidAmount, Ledger, LedgerError, UnknownAccount
from ledger.errors import DuplicateAccount, UnknownTransaction


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.open_account("alice", 10_000)
        self.ledger.open_account("bob")

    def test_open_account_and_balance(self):
        self.assertEqual(self.ledger.balance("alice"), 10_000)
        self.assertEqual(self.ledger.balance("bob"), 0)
        self.assertEqual(self.ledger.accounts(), ["alice", "bob"])

    def test_duplicate_account_rejected(self):
        with self.assertRaises(DuplicateAccount):
            self.ledger.open_account("alice")

    def test_transfer_moves_money_and_returns_sequential_ids(self):
        first = self.ledger.transfer("alice", "bob", 2_500, memo="rent")
        second = self.ledger.transfer("bob", "alice", 500)
        self.assertEqual((first, second), ("t1", "t2"))
        self.assertEqual(self.ledger.balance("alice"), 8_000)
        self.assertEqual(self.ledger.balance("bob"), 2_000)

    def test_overdraft_rejected_without_side_effects(self):
        with self.assertRaises(InsufficientFunds):
            self.ledger.transfer("bob", "alice", 1)
        self.assertEqual(self.ledger.balance("bob"), 0)
        self.assertEqual(self.ledger.history("bob"), [])

    def test_amount_must_be_positive_integer(self):
        for bad in (0, -5, 1.5, True, "100"):
            with self.subTest(amount=bad):
                with self.assertRaises(InvalidAmount):
                    self.ledger.transfer("alice", "bob", bad)

    def test_unknown_account(self):
        with self.assertRaises(UnknownAccount):
            self.ledger.transfer("alice", "carol", 100)
        with self.assertRaises(UnknownAccount):
            self.ledger.balance("carol")

    def test_self_transfer_rejected(self):
        with self.assertRaises(LedgerError):
            self.ledger.transfer("alice", "alice", 100)

    def test_history_and_lookup(self):
        self.ledger.open_account("carol")
        t1 = self.ledger.transfer("alice", "bob", 100, memo="lunch")
        t2 = self.ledger.transfer("alice", "carol", 200)
        t3 = self.ledger.transfer("bob", "carol", 50)
        self.assertEqual([t.id for t in self.ledger.history("bob")], [t1, t3])
        self.assertEqual([t.id for t in self.ledger.history("carol")], [t2, t3])
        txn = self.ledger.transaction(t1)
        self.assertEqual((txn.src, txn.dst, txn.amount, txn.memo), ("alice", "bob", 100, "lunch"))
        with self.assertRaises(UnknownTransaction):
            self.ledger.transaction("t99")
