import dataclasses
import unittest

from ledger import Transaction


class TransactionTests(unittest.TestCase):
    def test_transactions_are_immutable(self):
        txn = Transaction("t1", "alice", "bob", 100)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            txn.amount = 5

    def test_involves(self):
        txn = Transaction("t1", "alice", "bob", 100)
        self.assertTrue(txn.involves("alice"))
        self.assertTrue(txn.involves("bob"))
        self.assertFalse(txn.involves("carol"))
