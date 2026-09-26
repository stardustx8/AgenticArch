import unittest

from invoicing.format import format_money
from invoicing.models import LineItem
from invoicing.totals import invoice_totals


class TotalsTest(unittest.TestCase):
    def test_simple_invoice(self):
        items = [LineItem("widget", 5.0, 4, 0.2), LineItem("gadget", 2.5, 2, 0.0)]
        t = invoice_totals(items)
        self.assertEqual(t["net"], 25.0)
        self.assertEqual(t["tax"], 4.0)
        self.assertEqual(t["gross"], 29.0)

    def test_empty(self):
        self.assertEqual(invoice_totals([])["gross"], 0)

    def test_format(self):
        self.assertEqual(format_money(1234.5), "EUR 1,234.50")
        self.assertEqual(format_money(0, "USD"), "USD 0.00")


if __name__ == "__main__":
    unittest.main()
