import unittest

from pennybank import Account, InsufficientFunds


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.acct = Account("alice")

    def test_deposit_and_withdraw_update_balance(self):
        self.acct.deposit(100)
        self.acct.withdraw(30)
        self.assertEqual(self.acct.balance(), 70)

    def test_history_records_entries_in_order(self):
        self.acct.deposit(50)
        self.acct.withdraw(20)
        self.acct.deposit(5)
        self.assertEqual(
            self.acct.history(),
            [("deposit", 50), ("withdrawal", 20), ("deposit", 5)],
        )

    def test_history_is_a_copy(self):
        self.acct.deposit(10)
        self.acct.history().clear()
        self.assertEqual(len(self.acct.history()), 1)

    def test_overdraw_raises_and_leaves_balance(self):
        self.acct.deposit(40)
        with self.assertRaises(InsufficientFunds):
            self.acct.withdraw(41)
        self.assertEqual(self.acct.balance(), 40)
        self.assertEqual(len(self.acct.history()), 1)

    def test_non_positive_amounts_rejected(self):
        with self.assertRaises(ValueError):
            self.acct.deposit(0)
        with self.assertRaises(ValueError):
            self.acct.withdraw(-5)
        self.assertEqual(self.acct.history(), [])

    def test_owner_required(self):
        with self.assertRaises(ValueError):
            Account("")


if __name__ == "__main__":
    unittest.main()
