import unittest
from datetime import date
from decimal import Decimal

from fxledger.ledger import convert, ledger_total
from fxledger.money import Money
from fxledger.rates import RateTable

D = date(2024, 1, 2)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.rates = RateTable()
        self.rates.add(D, "USD", "EUR", "0.9")

    def test_money_coerces_to_decimal(self):
        self.assertEqual(Money("1.50", "EUR").amount, Decimal("1.50"))
        self.assertEqual(Money(2, "EUR").amount, Decimal("2"))

    def test_add_mismatch(self):
        with self.assertRaises(ValueError):
            Money("1", "EUR") + Money("1", "USD")

    def test_convert_exact_date(self):
        self.assertEqual(convert(Money("100", "USD"), "EUR", D, self.rates), Money(Decimal("90.00"), "EUR"))

    def test_same_currency_untouched(self):
        m = Money("12.34", "EUR")
        self.assertEqual(convert(m, "EUR", D, self.rates), m)

    def test_missing_rate(self):
        with self.assertRaises(KeyError):
            self.rates.get(D, "USD", "GBP")

    def test_total(self):
        entries = [(D, Money("10.00", "USD")), (D, Money("1.00", "EUR"))]
        self.assertEqual(ledger_total(entries, "EUR", self.rates), Money(Decimal("10.00"), "EUR"))


if __name__ == "__main__":
    unittest.main()
