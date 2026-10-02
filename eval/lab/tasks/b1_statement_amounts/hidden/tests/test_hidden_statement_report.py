import unittest
from datetime import date
from decimal import Decimal

from statements.loader import load_transactions
from statements.report import format_summary, monthly_summary

CSV = """date,description,amount,currency
2024-01-03,Coffee,-3.50,USD
2024-01-05,Miete,"-1.234,56",eur
2024-01-09,Pending,,USD
2024-01-10,Refund,"(12,50 €)",EUR
2024-01-20,Blank,   ,EUR
2024-01-31,Salary,"$2,500.00",USD
2024-02-01,Gehalt,"3.100,00 EUR",EUR
2024-02-02,Tea,£4,GBP
"""


class LoaderTest(unittest.TestCase):
    def test_empty_amount_rows_skipped(self):
        txs = load_transactions(CSV)
        self.assertEqual([t.description for t in txs], ["Coffee", "Miete", "Refund", "Salary", "Gehalt", "Tea"])

    def test_european_amounts_loaded(self):
        txs = {t.description: t for t in load_transactions(CSV)}
        self.assertEqual(txs["Miete"].amount, Decimal("-1234.56"))
        self.assertEqual(txs["Miete"].currency, "EUR")
        self.assertEqual(txs["Refund"].amount, Decimal("-12.50"))
        self.assertEqual(txs["Gehalt"].amount, Decimal("3100.00"))
        self.assertEqual(txs["Gehalt"].date, date(2024, 2, 1))

    def test_bad_amount_still_raises(self):
        with self.assertRaises(ValueError):
            load_transactions("date,description,amount,currency\n2024-01-01,X,lots,EUR\n")


class SummaryTest(unittest.TestCase):
    def test_keyed_by_month_and_currency(self):
        summary = monthly_summary(load_transactions(CSV))
        self.assertEqual(summary, {
            ("2024-01", "USD"): Decimal("2496.50"),
            ("2024-01", "EUR"): Decimal("-1247.06"),
            ("2024-02", "EUR"): Decimal("3100.00"),
            ("2024-02", "GBP"): Decimal("4"),
        })

    def test_format_summary(self):
        summary = monthly_summary(load_transactions(CSV))
        self.assertEqual(format_summary(summary).splitlines(), [
            "2024-01 EUR: -1247.06",
            "2024-01 USD: 2496.50",
            "2024-02 EUR: 3100.00",
            "2024-02 GBP: 4.00",
        ])

    def test_empty(self):
        self.assertEqual(monthly_summary([]), {})
        self.assertEqual(format_summary({}), "")


if __name__ == "__main__":
    unittest.main()
