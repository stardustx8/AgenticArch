import unittest

from ledger import InsufficientFunds, Ledger, LedgerError


class ReversalTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.open_account("alice", 1_000)
        self.ledger.open_account("bob")
        self.ledger.open_account("carol")

    def snapshot(self):
        names = ("alice", "bob", "carol")
        return (
            {n: self.ledger.balance(n) for n in names},
            {n: [t.id for t in self.ledger.history(n)] for n in names},
        )

    def total(self):
        return sum(self.ledger.balance(n) for n in self.ledger.accounts())

    def test_reverse_moves_money_back(self):
        txn = self.ledger.transfer("alice", "bob", 250, memo="oops")
        rev = self.ledger.reverse(txn)
        self.assertNotEqual(rev, txn)
        self.assertEqual(self.ledger.balance("alice"), 1_000)
        self.assertEqual(self.ledger.balance("bob"), 0)
        record = self.ledger.transaction(rev)
        self.assertEqual((record.src, record.dst, record.amount), ("bob", "alice", 250))

    def test_reversal_appears_in_both_histories(self):
        txn = self.ledger.transfer("alice", "bob", 250)
        rev = self.ledger.reverse(txn)
        self.assertEqual([t.id for t in self.ledger.history("alice")], [txn, rev])
        self.assertEqual([t.id for t in self.ledger.history("bob")], [txn, rev])
        self.assertEqual(self.ledger.history("carol"), [])

    def test_transaction_can_only_be_reversed_once(self):
        txn = self.ledger.transfer("alice", "bob", 250)
        self.ledger.reverse(txn)
        before = self.snapshot()
        with self.assertRaises(LedgerError):
            self.ledger.reverse(txn)
        self.assertEqual(self.snapshot(), before)

    def test_reversal_cannot_be_reversed(self):
        txn = self.ledger.transfer("alice", "bob", 250)
        rev = self.ledger.reverse(txn)
        before = self.snapshot()
        with self.assertRaises(LedgerError):
            self.ledger.reverse(rev)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_transaction(self):
        self.ledger.transfer("alice", "bob", 250)
        before = self.snapshot()
        for bad in ("t999", "nope"):
            with self.subTest(txn_id=bad):
                with self.assertRaises(LedgerError):
                    self.ledger.reverse(bad)
        self.assertEqual(self.snapshot(), before)

    def test_reversal_respects_overdraft_rule(self):
        txn = self.ledger.transfer("alice", "bob", 300)
        self.ledger.transfer("bob", "carol", 200)
        before = self.snapshot()
        with self.assertRaises(InsufficientFunds):
            self.ledger.reverse(txn)
        self.assertEqual(self.snapshot(), before)

    def test_failed_reversal_can_be_retried_once_funded(self):
        txn = self.ledger.transfer("alice", "bob", 300)
        self.ledger.transfer("bob", "carol", 200)
        with self.assertRaises(InsufficientFunds):
            self.ledger.reverse(txn)
        self.ledger.transfer("carol", "bob", 200)
        self.ledger.reverse(txn)
        self.assertEqual(self.ledger.balance("alice"), 1_000)
        self.assertEqual(self.ledger.balance("bob"), 0)
        self.assertEqual(self.ledger.balance("carol"), 0)
        with self.assertRaises(LedgerError):
            self.ledger.reverse(txn)

    def test_reversing_older_transaction_leaves_later_ones_alone(self):
        t1 = self.ledger.transfer("alice", "bob", 100)
        t2 = self.ledger.transfer("alice", "bob", 50)
        self.ledger.reverse(t1)
        self.assertEqual(self.ledger.balance("bob"), 50)
        self.assertEqual(self.ledger.balance("alice"), 950)
        self.ledger.reverse(t2)
        self.assertEqual(self.ledger.balance("bob"), 0)
        self.assertEqual(self.ledger.balance("alice"), 1_000)

    def test_ids_remain_unique(self):
        t1 = self.ledger.transfer("alice", "bob", 100)
        rev = self.ledger.reverse(t1)
        t3 = self.ledger.transfer("alice", "carol", 100)
        self.assertEqual(len({t1, rev, t3}), 3)
        self.assertEqual(self.ledger.transaction(t3).dst, "carol")
        self.assertEqual(self.ledger.transaction(rev).dst, "alice")

    def test_money_is_conserved(self):
        total = self.total()
        t1 = self.ledger.transfer("alice", "bob", 400, idempotency_key="a")
        self.ledger.transfer("alice", "bob", 400, idempotency_key="a")
        t2 = self.ledger.transfer("bob", "carol", 150)
        self.ledger.reverse(t2)
        with self.assertRaises(InsufficientFunds):
            self.ledger.transfer("carol", "alice", 1)
        self.ledger.reverse(t1)
        with self.assertRaises(LedgerError):
            self.ledger.reverse(t1)
        self.assertEqual(self.total(), total)
        self.assertEqual(self.ledger.balance("alice"), 1_000)
