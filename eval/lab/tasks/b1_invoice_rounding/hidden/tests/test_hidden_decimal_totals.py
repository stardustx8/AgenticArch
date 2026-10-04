import unittest
from decimal import Decimal

from invoicing.format import format_money
from invoicing.models import LineItem
from invoicing.totals import invoice_totals, line_net, line_tax


class DecimalTotalsTest(unittest.TestCase):
    def test_line_net_half_up_from_float(self):
        self.assertEqual(line_net(LineItem("a", 1.005, 1)), Decimal("1.01"))
        self.assertEqual(line_net(LineItem("b", 2.675, 1)), Decimal("2.68"))

    def test_line_net_is_decimal_with_cents(self):
        net = line_net(LineItem("a", 0.1, 3))
        self.assertIsInstance(net, Decimal)
        self.assertEqual(net, Decimal("0.30"))
        self.assertEqual(net.as_tuple().exponent, -2)

    def test_accepts_strings_and_ints(self):
        self.assertEqual(line_net(LineItem("a", "19.99", 3)), Decimal("59.97"))
        self.assertEqual(line_net(LineItem("a", 7, 2)), Decimal("14.00"))
        self.assertEqual(line_tax(LineItem("a", "10.00", 3, "0.075")), Decimal("2.25"))

    def test_line_tax_rounds_half_up(self):
        # 12.50 * 1% = 0.125 -> 0.13 (not banker's 0.12)
        self.assertEqual(line_tax(LineItem("a", "12.50", 1, "0.01")), Decimal("0.13"))
        self.assertEqual(line_tax(LineItem("a", 0.5, 1, 0.25)), Decimal("0.13"))

    def test_tax_rounded_per_line_before_summing(self):
        items = [LineItem("a", "12.50", 1, "0.01"), LineItem("b", "12.50", 1, "0.01")]
        totals = invoice_totals(items)
        self.assertEqual(totals["net"], Decimal("25.00"))
        self.assertEqual(totals["tax"], Decimal("0.26"))
        self.assertEqual(totals["gross"], Decimal("25.26"))

    def test_totals_are_decimals_without_drift(self):
        items = [LineItem(f"i{n}", 0.1, 1, 0.2) for n in range(10)]
        totals = invoice_totals(items)
        for key in ("net", "tax", "gross"):
            self.assertIsInstance(totals[key], Decimal)
        self.assertEqual(totals["net"], Decimal("1.00"))
        self.assertEqual(totals["tax"], Decimal("0.20"))
        self.assertEqual(totals["gross"], Decimal("1.20"))

    def test_empty_invoice_is_decimal_zero(self):
        totals = invoice_totals([])
        self.assertEqual(totals, {"net": Decimal("0"), "tax": Decimal("0"), "gross": Decimal("0")})
        self.assertIsInstance(totals["gross"], Decimal)

    def test_format_money_with_decimal(self):
        self.assertEqual(format_money(Decimal("1234.5")), "EUR 1,234.50")
        self.assertEqual(format_money(Decimal("-0.13"), "USD"), "USD -0.13")


if __name__ == "__main__":
    unittest.main()
