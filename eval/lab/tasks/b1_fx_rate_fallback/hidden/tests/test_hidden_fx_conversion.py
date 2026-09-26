import unittest
from datetime import date
from decimal import Decimal

from fxledger.ledger import convert, ledger_total
from fxledger.money import Money
from fxledger.rates import RateTable


class RateFallbackTest(unittest.TestCase):
    def setUp(self):
        self.rates = RateTable()
        # added out of order on purpose
        self.rates.add(date(2024, 1, 8), "USD", "EUR", "0.95")
        self.rates.add(date(2024, 1, 5), "USD", "EUR", "0.90")
        self.rates.add(date(2024, 1, 2), "USD", "EUR", "0.80")

    def conv(self, amount, on):
        return convert(Money(amount, "USD"), "EUR", on, self.rates)

    def test_weekend_uses_previous_rate(self):
        self.assertEqual(self.conv("100", date(2024, 1, 7)).amount, Decimal("90.00"))
        self.assertEqual(self.conv("100", date(2024, 1, 4)).amount, Decimal("80.00"))
        self.assertEqual(self.conv("100", date(2024, 2, 1)).amount, Decimal("95.00"))

    def test_exact_date_still_used(self):
        self.assertEqual(self.conv("100", date(2024, 1, 8)).amount, Decimal("95.00"))
        self.assertEqual(self.conv("100", date(2024, 1, 5)).amount, Decimal("90.00"))

    def test_never_uses_future_rate(self):
        with self.assertRaises(KeyError):
            self.conv("100", date(2024, 1, 1))

    def test_unknown_pair_raises(self):
        with self.assertRaises(KeyError):
            convert(Money("1", "USD"), "GBP", date(2024, 1, 9), self.rates)


class InverseRateTest(unittest.TestCase):
    def setUp(self):
        self.rates = RateTable()
        self.rates.add(date(2024, 1, 2), "USD", "EUR", "0.9")
        self.rates.add(date(2024, 1, 2), "USD", "JPY", "150")

    def test_inverse_used_when_direct_missing(self):
        result = convert(Money("100", "EUR"), "USD", date(2024, 1, 2), self.rates)
        self.assertEqual(result, Money(Decimal("111.11"), "USD"))

    def test_inverse_with_fallback(self):
        result = convert(Money("10000", "JPY"), "USD", date(2024, 1, 6), self.rates)
        self.assertEqual(result.amount, Decimal("66.67"))

    def test_direct_preferred_on_same_day(self):
        self.rates.add(date(2024, 1, 2), "EUR", "USD", "1.12")
        result = convert(Money("100", "EUR"), "USD", date(2024, 1, 2), self.rates)
        self.assertEqual(result.amount, Decimal("112.00"))


class MinorUnitsTest(unittest.TestCase):
    def setUp(self):
        self.d = date(2024, 1, 2)
        self.rates = RateTable()
        self.rates.add(self.d, "USD", "JPY", "150.125")
        self.rates.add(self.d, "USD", "KWD", "0.30745")
        self.rates.add(self.d, "EUR", "USD", "1.0945")

    def test_jpy_has_no_decimals(self):
        result = convert(Money("100", "USD"), "JPY", self.d, self.rates)
        self.assertEqual(result.currency, "JPY")
        self.assertEqual(str(result.amount), "15013")

    def test_kwd_has_three_decimals(self):
        result = convert(Money("10", "USD"), "KWD", self.d, self.rates)
        self.assertEqual(str(result.amount), "3.075")

    def test_two_decimals_half_up(self):
        # 10 * 1.0945 = 10.945 -> 10.95 (half-up, not banker's 10.94)
        result = convert(Money("10", "EUR"), "USD", self.d, self.rates)
        self.assertEqual(str(result.amount), "10.95")


class LedgerTotalTest(unittest.TestCase):
    def test_each_entry_rounded_before_summing(self):
        rates = RateTable()
        d = date(2024, 1, 2)
        rates.add(d, "USD", "EUR", "0.9")
        entries = [(d, Money("0.05", "USD"))] * 3 + [(d, Money("1.00", "EUR"))]
        # each 0.045 -> 0.05, so 0.15 + 1.00
        self.assertEqual(ledger_total(entries, "EUR", rates), Money(Decimal("1.15"), "EUR"))

    def test_total_in_jpy_with_fallback_and_inverse(self):
        rates = RateTable()
        rates.add(date(2024, 1, 5), "JPY", "USD", "0.0064")
        entries = [
            (date(2024, 1, 7), Money("1.00", "USD")),  # 156.25 -> 156
            (date(2024, 1, 7), Money("1.01", "USD")),  # 157.8125 -> 158
            (date(2024, 1, 8), Money("500", "JPY")),
        ]
        total = ledger_total(entries, "JPY", rates)
        self.assertEqual(total.currency, "JPY")
        self.assertEqual(str(total.amount), "814")

    def test_empty_ledger(self):
        self.assertEqual(ledger_total([], "USD", RateTable()).amount, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
