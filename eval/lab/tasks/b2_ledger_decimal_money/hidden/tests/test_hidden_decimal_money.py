import unittest
from decimal import Decimal

from pennybank import Account, InsufficientFunds, apply_monthly_fee


def is_two_place_decimal(value):
    return isinstance(value, Decimal) and value.as_tuple().exponent == -2


class DecimalBalanceTests(unittest.TestCase):
    def setUp(self):
        self.acct = Account("erin")

    def assertUnchanged(self, balance, entries):
        self.assertEqual(self.acct.balance(), balance)
        self.assertEqual(len(self.acct.history()), entries)

    def test_ten_dimes_make_exactly_one(self):
        for _ in range(10):
            self.acct.deposit("0.10")
        self.assertIsInstance(self.acct.balance(), Decimal)
        self.assertEqual(self.acct.balance(), Decimal("1.00"))
        self.assertEqual(str(self.acct.balance()), "1.00")

    def test_classic_float_drift_is_gone(self):
        self.acct.deposit("0.1")
        self.acct.deposit("0.2")
        self.assertEqual(str(self.acct.balance()), "0.30")
        self.acct.withdraw("0.3")
        self.assertEqual(self.acct.balance(), Decimal("0"))
        self.assertEqual(str(self.acct.balance()), "0.00")

    def test_new_account_balance_is_two_place_zero(self):
        self.assertTrue(is_two_place_decimal(self.acct.balance()))
        self.assertEqual(str(self.acct.balance()), "0.00")

    def test_int_deposit_is_stored_with_two_places(self):
        self.acct.deposit(100)
        self.assertTrue(is_two_place_decimal(self.acct.balance()))
        self.assertEqual(str(self.acct.balance()), "100.00")

    def test_decimal_and_string_amounts_accepted(self):
        self.acct.deposit(Decimal("1.50"))
        self.acct.deposit("1.5")
        self.acct.deposit(Decimal("2"))
        self.acct.deposit("0.05")
        self.assertEqual(str(self.acct.balance()), "5.05")
        self.acct.withdraw("0.5")
        self.acct.withdraw(Decimal("1.05"))
        self.acct.withdraw(1)
        self.assertEqual(str(self.acct.balance()), "2.50")

    def test_history_amounts_are_two_place_decimals(self):
        self.acct.deposit(3)
        self.acct.deposit("0.1")
        self.acct.withdraw(Decimal("1.25"))
        history = self.acct.history()
        self.assertEqual([kind for kind, _ in history], ["deposit", "deposit", "withdrawal"])
        self.assertEqual([str(amount) for _, amount in history], ["3.00", "0.10", "1.25"])
        for _, amount in history:
            self.assertTrue(is_two_place_decimal(amount), repr(amount))

    def test_floats_rejected_with_type_error(self):
        self.acct.deposit(5)
        for bad in (1.5, 0.1, 2.0):
            with self.subTest(amount=bad):
                with self.assertRaises(TypeError):
                    self.acct.deposit(bad)
                with self.assertRaises(TypeError):
                    self.acct.withdraw(bad)
        self.assertUnchanged(Decimal("5.00"), 1)
        self.assertNotIsInstance(self.acct.balance(), float)

    def test_non_numeric_strings_rejected(self):
        self.acct.deposit(5)
        for bad in ("abc", "", "1.2.3", "ten"):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.acct.deposit(bad)
                with self.assertRaises(ValueError):
                    self.acct.withdraw(bad)
        self.assertUnchanged(Decimal("5.00"), 1)

    def test_non_finite_amounts_rejected(self):
        self.acct.deposit(5)
        for bad in ("NaN", "Infinity", "-Infinity", Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.acct.deposit(bad)
                with self.assertRaises(ValueError):
                    self.acct.withdraw(bad)
        self.assertUnchanged(Decimal("5.00"), 1)

    def test_more_than_two_decimal_places_rejected(self):
        self.acct.deposit(5)
        for bad in ("1.005", Decimal("0.001"), "2.999", Decimal("1.234")):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.acct.deposit(bad)
                with self.assertRaises(ValueError):
                    self.acct.withdraw(bad)
        self.assertUnchanged(Decimal("5.00"), 1)

    def test_non_positive_amounts_rejected(self):
        self.acct.deposit(5)
        for bad in ("0", "0.00", "-1.00", Decimal("-1"), Decimal("0"), 0, -3):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.acct.deposit(bad)
                with self.assertRaises(ValueError):
                    self.acct.withdraw(bad)
        self.assertUnchanged(Decimal("5.00"), 1)

    def test_overdraw_with_decimal_amounts(self):
        self.acct.deposit("100.00")
        with self.assertRaises(InsufficientFunds):
            self.acct.withdraw("100.01")
        self.assertEqual(str(self.acct.balance()), "100.00")
        self.assertEqual(len(self.acct.history()), 1)
        self.acct.withdraw("100")
        self.assertEqual(str(self.acct.balance()), "0.00")


class HalfUpFeeTests(unittest.TestCase):
    def charge(self, balance, percent):
        acct = Account("gina")
        acct.deposit(balance)
        fee = apply_monthly_fee(acct, percent)
        return acct, fee

    def assertCharged(self, acct, fee, expected_fee, expected_balance):
        self.assertEqual(fee, Decimal(expected_fee))
        self.assertEqual(str(acct.balance()), expected_balance)
        kind, amount = acct.history()[-1]
        self.assertEqual(kind, "withdrawal")
        self.assertEqual(str(amount), expected_fee)

    def test_fraction_below_half_rounds_down(self):
        acct, fee = self.charge("10.10", Decimal("2.5"))  # 0.2525
        self.assertCharged(acct, fee, "0.25", "9.85")

    def test_sub_cent_fee_rounds_up(self):
        acct, fee = self.charge("0.30", Decimal("2.5"))  # 0.0075
        self.assertCharged(acct, fee, "0.01", "0.29")

    def test_exact_half_cent_rounds_up_not_to_even(self):
        acct, fee = self.charge("0.10", 5)  # 0.005
        self.assertCharged(acct, fee, "0.01", "0.09")
        acct, fee = self.charge("50.50", 1)  # 0.505
        self.assertCharged(acct, fee, "0.51", "49.99")
        acct, fee = self.charge("10.00", Decimal("0.25"))  # 0.025
        self.assertCharged(acct, fee, "0.03", "9.97")

    def test_fee_below_half_cent_is_not_charged(self):
        acct, fee = self.charge("0.10", Decimal("4.9"))  # 0.0049
        self.assertEqual(fee, 0)
        self.assertEqual(str(acct.balance()), "0.10")
        self.assertEqual(len(acct.history()), 1)


if __name__ == "__main__":
    unittest.main()
