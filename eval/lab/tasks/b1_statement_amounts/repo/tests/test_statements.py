import unittest
from datetime import date
from decimal import Decimal

from statements.amounts import parse_amount
from statements.loader import load_transactions

CSV = """date,description,amount,currency
2024-01-03,Coffee,-3.50,usd
2024-01-15,Salary,"$2,500.00",USD
2024-02-01,Rent,-1200,USD
"""


class AmountTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_amount("12.34"), Decimal("12.34"))
        self.assertEqual(parse_amount(" -7 "), Decimal("-7"))

    def test_dollar_and_thousands(self):
        self.assertEqual(parse_amount("$1,234.56"), Decimal("1234.56"))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_amount("abc")


class LoaderTest(unittest.TestCase):
    def test_load(self):
        txs = load_transactions(CSV)
        self.assertEqual(len(txs), 3)
        self.assertEqual(txs[0].date, date(2024, 1, 3))
        self.assertEqual(txs[0].currency, "USD")
        self.assertEqual(txs[1].amount, Decimal("2500.00"))


if __name__ == "__main__":
    unittest.main()
