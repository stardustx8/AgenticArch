import unittest

import ledger.errors as errors
from ledger import InsufficientFunds, InvalidAmount, Ledger, LedgerError


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.open_account("alice", 1_000)
        self.ledger.open_account("bob")
        self.ledger.open_account("carol", 5_000)

    def snapshot(self):
        names = ("alice", "bob", "carol")
        return (
            {n: self.ledger.balance(n) for n in names},
            {n: [t.id for t in self.ledger.history(n)] for n in names},
        )

    def test_retry_returns_original_id_without_moving_money(self):
        first = self.ledger.transfer("alice", "bob", 300, memo="rent", idempotency_key="k1")
        again = self.ledger.transfer("alice", "bob", 300, memo="rent", idempotency_key="k1")
        self.assertEqual(again, first)
        self.assertEqual(self.ledger.balance("alice"), 700)
        self.assertEqual(self.ledger.balance("bob"), 300)
        self.assertEqual([t.id for t in self.ledger.history("alice")], [first])

    def test_retry_returns_original_even_if_it_could_not_be_funded_now(self):
        first = self.ledger.transfer("alice", "bob", 1_000, idempotency_key="k1")
        self.assertEqual(self.ledger.balance("alice"), 0)
        self.assertEqual(self.ledger.transfer("alice", "bob", 1_000, idempotency_key="k1"), first)
        self.assertEqual(self.ledger.balance("alice"), 0)
        self.assertEqual(self.ledger.balance("bob"), 1_000)

    def test_conflict_is_a_ledger_error(self):
        self.assertTrue(issubclass(errors.IdempotencyConflict, LedgerError))

    def test_reusing_key_with_different_arguments_conflicts(self):
        self.ledger.transfer("alice", "bob", 300, memo="rent", idempotency_key="k1")
        before = self.snapshot()
        variants = [
            ("alice", "bob", 301, "rent"),
            ("alice", "carol", 300, "rent"),
            ("carol", "bob", 300, "rent"),
            ("alice", "bob", 300, "deposit"),
        ]
        for src, dst, amount, memo in variants:
            with self.subTest(src=src, dst=dst, amount=amount, memo=memo):
                with self.assertRaises(errors.IdempotencyConflict):
                    self.ledger.transfer(src, dst, amount, memo=memo, idempotency_key="k1")
                self.assertEqual(self.snapshot(), before)

    def test_failed_transfer_does_not_burn_key(self):
        before = self.snapshot()
        with self.assertRaises(InsufficientFunds):
            self.ledger.transfer("alice", "bob", 1_500, idempotency_key="k1")
        self.assertEqual(self.snapshot(), before)
        self.ledger.transfer("carol", "alice", 500)
        txn = self.ledger.transfer("alice", "bob", 1_500, idempotency_key="k1")
        self.assertEqual(self.ledger.balance("alice"), 0)
        self.assertEqual(self.ledger.balance("bob"), 1_500)
        self.assertEqual(self.ledger.transfer("alice", "bob", 1_500, idempotency_key="k1"), txn)
        self.assertEqual(self.ledger.balance("bob"), 1_500)

    def test_failed_transfer_leaves_key_free_for_other_arguments(self):
        with self.assertRaises(InsufficientFunds):
            self.ledger.transfer("alice", "bob", 1_500, idempotency_key="k1")
        txn = self.ledger.transfer("alice", "bob", 400, idempotency_key="k1")
        self.assertEqual(self.ledger.balance("bob"), 400)
        with self.assertRaises(errors.IdempotencyConflict):
            self.ledger.transfer("alice", "bob", 500, idempotency_key="k1")
        self.assertEqual(self.ledger.transfer("alice", "bob", 400, idempotency_key="k1"), txn)
        self.assertEqual(self.ledger.balance("bob"), 400)

    def test_invalid_transfer_does_not_burn_key(self):
        with self.assertRaises(InvalidAmount):
            self.ledger.transfer("alice", "bob", 0, idempotency_key="k1")
        with self.assertRaises(LedgerError):
            self.ledger.transfer("alice", "alice", 10, idempotency_key="k1")
        txn = self.ledger.transfer("alice", "bob", 10, idempotency_key="k1")
        self.assertEqual(self.ledger.transaction(txn).amount, 10)
        self.assertEqual(self.ledger.balance("bob"), 10)

    def test_distinct_keys_are_independent(self):
        first = self.ledger.transfer("alice", "bob", 100, idempotency_key="k1")
        second = self.ledger.transfer("alice", "bob", 100, idempotency_key="k2")
        self.assertNotEqual(first, second)
        self.assertEqual(self.ledger.balance("bob"), 200)

    def test_keyed_and_unkeyed_transfers_coexist(self):
        keyed = self.ledger.transfer("alice", "bob", 100, idempotency_key="k1")
        plain1 = self.ledger.transfer("alice", "bob", 100)
        plain2 = self.ledger.transfer("alice", "bob", 100)
        self.assertEqual(len({keyed, plain1, plain2}), 3)
        self.assertEqual(self.ledger.transfer("alice", "bob", 100, idempotency_key="k1"), keyed)
        self.assertEqual(self.ledger.balance("bob"), 300)
        self.assertEqual(len(self.ledger.history("bob")), 3)
