import unittest
from decimal import Decimal

from shop import Catalog, Product, checkout, refund_amount


class HalfUpRoundingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog([
            Product('PEN', 'pen', Decimal('0.835'), 'exempt'),
            Product('CLIP', 'clip', Decimal('0.845'), 'exempt'),
            Product('PAD', 'pad', Decimal('1.025'), 'exempt'),
            Product('PIN', 'pin', Decimal('0.125'), 'exempt'),
            Product('INK', 'ink', Decimal('0.835'), 'standard'),
        ])

    def test_line_total_rounds_half_up(self):
        order = checkout('h1', 'DE', [('PEN', 3)], self.catalog)
        self.assertEqual(order.lines[0].line_total, Decimal('2.51'))
        self.assertEqual(order.total, Decimal('2.51'))

    def test_single_unit_rounds_half_up(self):
        order = checkout('h2', 'DE', [('CLIP', 1)], self.catalog)
        self.assertEqual(order.total, Decimal('0.85'))

    def test_taxed_line_uses_half_up_line_total(self):
        order = checkout('h3', 'DE', [('INK', 3)], self.catalog)
        self.assertEqual(order.subtotal, Decimal('2.51'))
        self.assertEqual(order.tax_total, Decimal('0.48'))

    def test_refund_rounds_half_up(self):
        order = checkout('h4', 'DE', [('PAD', 4)], self.catalog)
        self.assertEqual(order.lines[0].line_total, Decimal('4.10'))
        self.assertEqual(refund_amount(order, 'PAD', 1), Decimal('1.03'))

    def test_refund_of_half_cent_unit(self):
        order = checkout('h5', 'DE', [('PIN', 2)], self.catalog)
        self.assertEqual(refund_amount(order, 'PIN', 1), Decimal('0.13'))

    def test_full_refund_matches_line(self):
        order = checkout('h6', 'DE', [('PAD', 4)], self.catalog)
        self.assertEqual(refund_amount(order, 'PAD', 4), Decimal('4.10'))


if __name__ == '__main__':
    unittest.main()
