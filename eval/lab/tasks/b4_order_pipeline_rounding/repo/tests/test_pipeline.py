import tempfile
import unittest
from decimal import Decimal

from shop import Catalog, OrderRepository, PercentOff, Product, checkout, refund_amount
from shop.money import quantize_money
from shop.pricing import unit_price_for


def make_catalog():
    return Catalog([
        Product('A', 'apple', Decimal('2.00'), 'food'),
        Product('B', 'book', Decimal('10.00'), 'standard',
                price_breaks=((5, Decimal('9.00')), (10, Decimal('8.00')))),
        Product('G', 'gift card', Decimal('25.00'), 'exempt'),
    ])


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.catalog = make_catalog()

    def test_basic_totals(self):
        order = checkout('o1', 'DE', [('A', 3), ('B', 1)], self.catalog)
        self.assertEqual(order.subtotal, Decimal('16.00'))
        self.assertEqual(order.tax_total, Decimal('2.32'))
        self.assertEqual(order.total, Decimal('18.32'))

    def test_price_breaks(self):
        book = self.catalog.get('B')
        self.assertEqual(unit_price_for(book, 4), Decimal('10.00'))
        self.assertEqual(unit_price_for(book, 5), Decimal('9.00'))
        self.assertEqual(unit_price_for(book, 12), Decimal('8.00'))

    def test_line_uses_break_price(self):
        order = checkout('o2', 'DE', [('B', 10)], self.catalog)
        self.assertEqual(order.lines[0].line_total, Decimal('80.00'))

    def test_percent_coupon(self):
        order = checkout('o3', 'DE', [('B', 2)], self.catalog, coupon=PercentOff(10))
        self.assertEqual(order.discount_total, Decimal('2.00'))
        self.assertEqual(order.tax_total, Decimal('3.42'))
        self.assertEqual(order.total, Decimal('21.42'))

    def test_exempt_category(self):
        order = checkout('o4', 'NL', [('G', 1)], self.catalog)
        self.assertEqual(order.tax_total, Decimal('0'))
        self.assertEqual(order.total, Decimal('25.00'))

    def test_unknown_sku(self):
        with self.assertRaises(KeyError):
            checkout('o5', 'DE', [('Z', 1)], self.catalog)

    def test_non_positive_quantity(self):
        with self.assertRaises(ValueError):
            checkout('o6', 'DE', [('A', 0)], self.catalog)

    def test_quantize_money_rounds_half_up(self):
        self.assertEqual(quantize_money('2.505'), Decimal('2.51'))
        self.assertEqual(quantize_money(Decimal('0.125')), Decimal('0.13'))


class RepositoryTests(unittest.TestCase):
    def test_round_trip_with_percent_coupon(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = OrderRepository(tmp)
            order = checkout('o7', 'DE', [('A', 2), ('B', 5)], make_catalog(),
                             coupon=PercentOff(10), repository=repo)
            loaded = repo.load('o7')
            self.assertEqual(loaded.total, order.total)
            self.assertEqual(loaded.discount_total, order.discount_total)
            self.assertIsInstance(loaded.coupon, PercentOff)
            self.assertEqual(loaded.coupon.value, Decimal('10'))


class RefundTests(unittest.TestCase):
    def setUp(self):
        self.order = checkout('o8', 'DE', [('B', 2)], make_catalog())

    def test_refund_whole_line(self):
        self.assertEqual(refund_amount(self.order, 'B', 2), Decimal('23.80'))

    def test_refund_single_unit(self):
        self.assertEqual(refund_amount(self.order, 'B', 1), Decimal('11.90'))

    def test_refund_rejects_bad_quantity(self):
        with self.assertRaises(ValueError):
            refund_amount(self.order, 'B', 3)
        with self.assertRaises(KeyError):
            refund_amount(self.order, 'A', 1)


if __name__ == '__main__':
    unittest.main()
