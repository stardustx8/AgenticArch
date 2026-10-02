import unittest
from decimal import Decimal

from reports.money import AmountError, format_money, parse_amount, round_cents


class MoneyTest(unittest.TestCase):
    def test_parse_amount_variants(self):
        self.assertEqual(parse_amount('1,234.50'), Decimal('1234.50'))
        self.assertEqual(parse_amount(' -3 '), Decimal('-3'))
        self.assertEqual(parse_amount('(12.00)'), Decimal('-12.00'))

    def test_parse_amount_rejects_garbage(self):
        for bad in ('', 'abc', 'NaN', '1.2.3'):
            with self.subTest(bad=bad):
                with self.assertRaises(AmountError):
                    parse_amount(bad)

    def test_round_cents(self):
        self.assertEqual(round_cents(Decimal('1.234')), Decimal('1.23'))
        self.assertEqual(round_cents(Decimal('1.236')), Decimal('1.24'))

    def test_format_money(self):
        self.assertEqual(format_money(Decimal('1234.5'), 'USD'), 'USD 1,234.50')
        self.assertEqual(format_money(Decimal('-2'), 'EUR'), 'EUR -2.00')
