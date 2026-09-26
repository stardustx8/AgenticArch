import unittest

from pennybank import Account, apply_monthly_fee, charge_all


class MonthlyFeeTests(unittest.TestCase):
    def test_fee_is_withdrawn(self):
        acct = Account("bob")
        acct.deposit(200)
        fee = apply_monthly_fee(acct, 1)
        self.assertEqual(fee, 2)
        self.assertEqual(acct.balance(), 198)
        self.assertEqual(acct.history()[-1], ("withdrawal", 2))

    def test_empty_account_is_not_charged(self):
        acct = Account("carol")
        self.assertEqual(apply_monthly_fee(acct, 3), 0)
        self.assertEqual(acct.history(), [])

    def test_negative_percent_rejected(self):
        acct = Account("dave")
        acct.deposit(10)
        with self.assertRaises(ValueError):
            apply_monthly_fee(acct, -1)
        self.assertEqual(acct.balance(), 10)

    def test_charge_all_is_keyed_by_owner(self):
        first, second = Account("erin"), Account("frank")
        first.deposit(100)
        second.deposit(300)
        self.assertEqual(charge_all([first, second], 2), {"erin": 2, "frank": 6})
        self.assertEqual(second.balance(), 294)


if __name__ == "__main__":
    unittest.main()
